import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from halala import pipeline
from halala.config import load_config
from halala.data import Item, load_jsonl, make_synthetic_arith, seal, write_jsonl
from halala.dialect_audit import cmd_dialect_audit, cmd_dialect_rewrite, sign_test, wilson
from halala.measure import ALL_ARMS, cmd_measure
from halala.prompt_eval import LABELS as PROMPT_LABELS
from halala.prompt_eval import cmd_prompt_eval
from halala.rewrite_eval import LABELS, cmd_rewrite_eval, similarity


def _quiet():
    return contextlib.ExitStack()


class SealTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source = root / "questions.jsonl"
        write_jsonl(self.source, make_synthetic_arith(90, seed=5))
        with contextlib.redirect_stdout(io.StringIO()):
            self.info = seal(self.source, root / "sealed", test_fraction=0.33, seed=13)
        self.cfg = load_config()
        self.cfg["run"].update(out_dir=str(root / "runs"), data=str(self.info["dev_path"]),
                               sealed=str(self.info["test_path"]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_split_is_by_group_and_disjoint(self):
        dev, test = load_jsonl(self.info["dev_path"]), load_jsonl(self.info["test_path"])
        self.assertEqual(len(dev) + len(test), 450)
        self.assertFalse({it.group_id for it in dev} & {it.group_id for it in test})
        self.assertTrue(20 <= self.info["test_groups"] <= 40, self.info["test_groups"])

    def test_resealing_needs_force(self):
        with self.assertRaises(SystemExit):
            seal(self.source, self.info["test_path"].parent, 0.33, 13)

    def test_sealed_split_needs_unseal_and_logs_it(self):
        with self.assertRaises(SystemExit):
            pipeline.cmd_collect(self.cfg, "sealed")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            pipeline.cmd_collect(self.cfg, "sealed", unseal=True)
        manifest = json.loads(self.info["manifest_path"].read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["unsealed"]), 1)
        self.assertTrue((Path(self.cfg["run"]["out_dir"]) / "default" / "collect_sealed.jsonl").exists())

    def test_edited_sealed_file_is_refused(self):
        with open(self.info["test_path"], "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": "x", "question": "What is 1 plus 1?", "answers": ["2"]}) + "\n")
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
            pipeline.cmd_collect(self.cfg, "sealed", unseal=True)

    def test_working_data_overlapping_the_sealed_set_is_refused(self):
        self.cfg["run"]["data"] = str(self.source)   # the full file, which contains the sealed questions
        with self.assertRaises(SystemExit):
            pipeline.load_splits(self.cfg)

    def test_rewrite_examples_must_not_contain_data_questions(self):
        examples = Path(self.tmp.name) / "examples.jsonl"
        leaked = load_jsonl(self.info["test_path"])[0]
        examples.write_text(json.dumps({"arabizi": leaked.question, "arabic": "x"}, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        self.cfg["cascade"]["arabizi_examples"] = str(examples)
        with self.assertRaises(SystemExit):
            pipeline.load_splits(self.cfg)


class RewriteEvalTest(unittest.TestCase):
    def test_every_arm_reports_and_the_best_case_uses_the_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "questions.jsonl"
            write_jsonl(data, make_synthetic_arith(12, seed=5))
            examples = Path(tmp) / "examples.jsonl"
            examples.write_text('{"arabizi": "wain el soog?", "arabic": "وين السوق؟"}\n', encoding="utf-8")
            cfg = load_config()
            cfg["run"].update(out_dir=tmp, data=str(data))
            with contextlib.redirect_stdout(io.StringIO()):
                md = cmd_rewrite_eval(cfg, str(examples))
            for label in LABELS.values():
                self.assertIn(label, md)
            self.assertTrue((Path(tmp) / "default" / "rewrite_eval.html").exists())

    def test_similarity(self):
        self.assertEqual(similarity("وش عاصمة السعودية؟", "وش عاصمة السعودية"), 1.0)
        self.assertLess(similarity("وش عاصمة السعودية؟", "الولد كم عمره؟"), 0.2)


class DialectAuditTest(unittest.TestCase):
    def test_reports_each_form_for_each_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "dialects.jsonl"
            write_jsonl(data, [Item(id=f"q{i}-{f}", group_id=f"q{i}", variant=f, question="ما عاصمة البلد؟",
                                    answers=["B"], choices=["جدة", "الرياض", "مكة", "الدمام"])
                               for i in range(20) for f in ("ENG", "MSA", "MAG")])
            cfg = load_config()
            cfg["run"]["out_dir"] = tmp
            with contextlib.redirect_stdout(io.StringIO()):
                md = cmd_dialect_audit(cfg, str(data))
            for label in ("mock-small", "mock-large", "Moroccan"):
                self.assertIn(label, md)

    def test_wilson_interval(self):
        low, high = wilson(0, 10)
        self.assertEqual(low, 0.0)
        self.assertTrue(0.25 < high < 0.35)


class DialectRewriteTest(unittest.TestCase):
    def test_reports_the_attempt_and_the_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "dialects.jsonl"
            forms = (("ENG", "Which is the capital?"), ("MSA", "ما العاصمة؟"), ("KSA", "وش العاصمة؟"))
            write_jsonl(data, [Item(id=f"q{i}-{f}", group_id=f"q{i}", variant=f, question=text, answers=["B"],
                                    choices=["جدة", "الرياض", "مكة", "الدمام"])
                               for i in range(20) for f, text in forms])
            dev = Path(tmp) / "dev.jsonl"
            write_jsonl(dev, make_synthetic_arith(12, seed=5))
            cfg = load_config()
            cfg["run"].update(out_dir=tmp, data=str(dev))
            with contextlib.redirect_stdout(io.StringIO()):
                md = cmd_dialect_rewrite(cfg, str(data))
            for text in ("Saudi, rewritten", "changed 20 of 20", "Dev najdi", "at least 5", "Result: "):
                self.assertIn(text, md)
            self.assertTrue((Path(tmp) / "default" / "dialect_rewrite.html").exists())

    def test_sign_test_matches_a_worked_case(self):
        self.assertAlmostEqual(sign_test(17, 4), 0.0072, places=4)
        self.assertEqual(sign_test(0, 0), 1.0)
        self.assertEqual(sign_test(1, 0), 1.0)


class PromptEvalTest(unittest.TestCase):
    def test_every_arm_reports_on_all_questions(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "questions.jsonl"
            write_jsonl(data, make_synthetic_arith(12, seed=5))
            cfg = load_config()
            cfg["run"].update(out_dir=tmp, data=str(data))
            cfg["cascade"]["arabizi"] = "rules"
            with contextlib.redirect_stdout(io.StringIO()):
                md = cmd_prompt_eval(cfg)
            for label in PROMPT_LABELS.values():
                self.assertIn(label, md)
            self.assertTrue((Path(tmp) / "default" / "prompt_eval.html").exists())


class MeasureTest(unittest.TestCase):
    def test_every_arm_runs_with_no_cache_in_either_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "questions.jsonl"
            write_jsonl(data, make_synthetic_arith(12, seed=5))
            cfg = load_config()
            cfg["run"].update(out_dir=tmp, data=str(data))
            cfg["cascade"]["arabizi"] = "rules"
            with contextlib.redirect_stdout(io.StringIO()):
                md = cmd_measure(cfg, list(ALL_ARMS), 4, False)
                cmd_measure(cfg, ["baseline", "none_first"], 4, True)
            for label in PROMPT_LABELS.values():
                self.assertIn(label, md)
            self.assertIn("20 dev questions", md)
            self.assertTrue((Path(tmp) / "default" / "measure_interleaved.md").exists())


class MultipleChoicePipelineTest(unittest.TestCase):
    def test_mock_collect_scores_letters(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "mcq.jsonl"
            write_jsonl(data, [
                Item(id=f"q{i}", group_id=f"q{i}", variant="msa", question=f"ما عاصمة البلد رقم {i}؟",
                     answers=["B"], choices=["جدة", "الرياض", "مكة", "الدمام"])
                for i in range(30)
            ])
            cfg = load_config()
            cfg["run"].update(out_dir=tmp, data=str(data), split_fractions={"train": 0.0, "calib": 0.0, "test": 1.0})
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                pipeline.cmd_collect(cfg, "test")
            with open(Path(tmp) / "default" / "collect_test.jsonl", encoding="utf-8") as f:
                records = [json.loads(line) for line in f]
            self.assertEqual(len(records), 30)
            self.assertIn("B. الرياض", records[0]["prompt"])
            # The mock large model answers the gold letter most of the time.
            self.assertGreater(sum(r["large_correct"] for r in records), 20)


if __name__ == "__main__":
    unittest.main()
