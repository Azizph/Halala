import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from halala.config import ROOT, load_config
from halala.data import Item, load_jsonl, seal, write_jsonl
from halala.dialect_audit import cmd_dialect_audit, cmd_scorecard, wilson
from halala.measure import cmd_check, cmd_fresh, cmd_measure, cmd_sealed, cmd_tax
from halala.messy import TYPING, cmd_messy, holds_up, retype
from halala.models import Completion
from halala.pipeline import SYSTEM_ANSWER, answer, load_dev, prepare, steps, usable_answer

SMOKE = ROOT / "data" / "smoke_parallel.jsonl"
ENGLISH = "What is the capital of Saudi Arabia?"
ARABIZI = "wesh 3asmat el sa3odiya?"


class Spy:
    """A model that records what it is sent and answers from a script."""

    def __init__(self, name: str, reply: str = "Riyadh"):
        self.name = name
        self.reply = reply
        self.seen: list[tuple[str, str]] = []

    def complete(self, system, user, temperature=0.0, sample=0, hint=None) -> Completion:
        self.seen.append((system, user))
        return Completion(self.reply, 10, 2, 0.5, active_s=0.25)


def quietly(call, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return call(*args, **kwargs)


def routed(route_english: bool) -> dict:
    cfg = load_config()
    cfg["cascade"]["route_english"] = route_english
    return cfg


class StepsTest(unittest.TestCase):
    def test_english_goes_to_the_small_model_when_there_is_room(self):
        small, large = Spy("small"), Spy("large")
        answer(ENGLISH, small, large, routed(True))
        self.assertEqual(small.seen, [(SYSTEM_ANSWER, ENGLISH)])
        self.assertEqual(large.seen, [])

    def test_english_stays_on_the_large_model_without_room(self):
        small, large = Spy("small"), Spy("large")
        answer(ENGLISH, small, large, routed(False))
        self.assertEqual(small.seen, [])
        self.assertEqual(len(large.seen), 1)

    def test_arabizi_is_rewritten_with_no_model_call(self):
        small, large = Spy("small"), Spy("large")
        events = list(steps(ARABIZI, small, large, routed(True)))
        rewrite = next(e for e in events if e["step"] == "rewrite")
        self.assertTrue(rewrite["rewritten"])
        self.assertEqual(small.seen, [])
        self.assertEqual([text for _, text in large.seen], [rewrite["prompt"]])
        self.assertNotIn("wesh", rewrite["prompt"])

    def test_arabic_goes_to_the_large_model_cleaned_and_not_rewritten(self):
        self.assertEqual(prepare("كم يطلع ١٥؟"), ("كم يطلع 15؟", False))
        small, large = Spy("small"), Spy("large")
        answer("كم يطلع ١٥؟", small, large, routed(True))
        self.assertEqual(small.seen, [])
        self.assertEqual([text for _, text in large.seen], ["كم يطلع 15؟"])

    def test_an_unusable_small_answer_falls_back_and_both_calls_are_paid_for(self):
        small, large = Spy("small", reply=""), Spy("large")
        result = answer(ENGLISH, small, large, routed(True))
        self.assertEqual(result["text"], "Riyadh")
        self.assertEqual(len(result["calls"]), 2)

    def test_the_free_check(self):
        self.assertFalse(usable_answer("  "))
        self.assertFalse(usable_answer("I'm sorry, I can't help with that."))
        self.assertTrue(usable_answer("الرياض"))


class SealTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source = root / "questions.jsonl"
        self.source.write_bytes(SMOKE.read_bytes())
        self.info = seal(self.source, root / "sealed", test_fraction=0.5, seed=13)
        self.cfg = load_config()
        self.cfg["run"].update(out_dir=str(root / "runs"), data=str(self.info["dev_path"]),
                               sealed=str(self.info["test_path"]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_split_is_by_group_and_disjoint(self):
        dev, test = load_jsonl(self.info["dev_path"]), load_jsonl(self.info["test_path"])
        self.assertEqual(len(dev) + len(test), 40)
        self.assertTrue(dev and test)
        self.assertFalse({it.group_id for it in dev} & {it.group_id for it in test})

    def test_resealing_needs_force(self):
        with self.assertRaises(SystemExit):
            seal(self.source, self.info["test_path"].parent, 0.5, 13)

    def test_sealed_run_needs_unseal_and_logs_it(self):
        with self.assertRaises(SystemExit):
            cmd_sealed(self.cfg, False)
        md = quietly(cmd_sealed, self.cfg, True)
        self.assertIn("Halala", md)
        manifest = json.loads(self.info["manifest_path"].read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["unsealed"]), 1)

    def test_edited_sealed_file_is_refused(self):
        with open(self.info["test_path"], "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": "x", "question": "What is 1 plus 1?", "answers": ["2"]}) + "\n")
        with self.assertRaises(SystemExit):
            quietly(cmd_sealed, self.cfg, True)

    def test_working_data_overlapping_the_sealed_set_is_refused(self):
        self.cfg["run"]["data"] = str(self.source)   # the full file, which contains the sealed questions
        with self.assertRaises(SystemExit):
            load_dev(self.cfg)


class MeasureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = load_config()
        self.cfg["run"]["out_dir"] = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_tax_reports_every_design_by_form(self):
        md = quietly(cmd_tax, self.cfg)
        for text in ("ALLaM alone", "With Halala", "| arabizi |"):
            self.assertIn(text, md)

    def test_check_passes_on_its_baseline_and_fails_on_a_fall(self):
        quietly(cmd_tax, self.cfg)
        quietly(cmd_check, self.cfg, True)
        self.assertEqual(quietly(cmd_check, self.cfg, False), 0)
        out = Path(self.tmp.name) / "default"
        baseline = json.loads((out / "baseline.json").read_text(encoding="utf-8"))
        baseline["en"]["correct"] += 5
        (out / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
        self.assertEqual(quietly(cmd_check, self.cfg, False), 1)

    def test_fresh_reports_each_question_and_the_detection(self):
        data = Path(self.tmp.name) / "fresh.jsonl"
        write_jsonl(data, [Item(id="f1", group_id="f1", variant="arabizi", question=ARABIZI, answers=["الرياض"],
                                meta={"arabic": "وش عاصمة السعودية؟"})])
        md = quietly(cmd_fresh, self.cfg, str(data))
        self.assertIn("Read by Halala as Arabizi: 1 of 1", md)
        self.assertIn("in proper Arabic", md)
        self.assertIn(ARABIZI, md)

    def test_measure_compares_mixed_traffic(self):
        md = quietly(cmd_measure, self.cfg, 4)
        self.assertIn("20 dev questions", md)
        self.assertIn("Halala", md)


class MessyTest(unittest.TestCase):
    def test_retyping_repeats_exactly_and_changes_the_text(self):
        item = Item(id="m1", group_id="m1", variant="arabizi", question=ARABIZI, answers=["الرياض"])
        self.assertEqual(retype(item, "as written"), ARABIZI)
        for kind in TYPING:
            self.assertEqual(retype(item, kind), retype(item, kind))
        for kind in set(TYPING) - {"as written", "all lower case, no punctuation"}:
            self.assertNotEqual(retype(item, kind), ARABIZI, kind)

    def test_a_way_of_typing_must_keep_two_thirds_and_stay_above_alone(self):
        self.assertTrue(holds_up(1, 16, 24))
        self.assertFalse(holds_up(1, 15, 24))
        self.assertFalse(holds_up(20, 16, 24))

    def test_messy_reports_every_way_of_typing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config()
            cfg["run"]["out_dir"] = tmp
            md = quietly(cmd_messy, cfg)
            for kind in TYPING:
                self.assertIn(f"| {kind} |", md)
            self.assertIn("75 Arabizi questions", md)


class DialectAuditTest(unittest.TestCase):
    def test_reports_each_form_for_each_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "dialects.jsonl"
            write_jsonl(data, [Item(id=f"q{i}-{f}", group_id=f"q{i}", variant=f, question="ما عاصمة البلد؟",
                                    answers=["B"], choices=["جدة", "الرياض", "مكة", "الدمام"])
                               for i in range(20) for f in ("ENG", "MSA", "MAG")])
            cfg = load_config()
            cfg["run"]["out_dir"] = tmp
            md = quietly(cmd_dialect_audit, cfg, str(data))
            for label in ("mock-small", "mock-large", "Moroccan"):
                self.assertIn(label, md)

    def test_scorecard_reports_every_model_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "dialects.jsonl"
            write_jsonl(data, [Item(id=f"q{i}-{f}", group_id=f"q{i}", variant=f, question="ما عاصمة البلد؟",
                                    answers=["B"], choices=["جدة", "الرياض", "مكة", "الدمام"])
                               for i in range(20) for f in ("ENG", "KSA")])
            cfg = load_config()
            cfg["run"]["out_dir"] = tmp
            md = quietly(cmd_scorecard, cfg, str(data), ["mock-large", "mock-other"])
            for label in ("mock-large", "mock-other", "Saudi", "Right answers out of 20"):
                self.assertIn(label, md)

    def test_wilson_interval(self):
        low, high = wilson(0, 10)
        self.assertEqual(low, 0.0)
        self.assertTrue(0.25 < high < 0.35)


if __name__ == "__main__":
    unittest.main()
