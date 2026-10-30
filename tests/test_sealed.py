import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from halala import pipeline
from halala.config import load_config
from halala.data import Item, load_jsonl, make_synthetic_arith, seal, write_jsonl
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
