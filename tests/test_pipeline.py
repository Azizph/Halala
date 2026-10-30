import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from halala import pipeline
from halala.config import load_config
from halala.data import make_synthetic_arith, write_jsonl
from halala.calibrate import losses_if_kept
from halala.policies import cost_per_success, drop_unprofitable, nearest_prior, simulate
from halala.report import inject_readme


def _config(tmp: str, groups: int, **cascade) -> dict:
    cfg = load_config()
    data = Path(tmp) / "data.jsonl"
    write_jsonl(data, make_synthetic_arith(groups, seed=7))
    cfg["run"]["out_dir"] = tmp
    cfg["run"]["data"] = str(data)
    cfg["cascade"].update(cascade)
    return cfg


class CacheTest(unittest.TestCase):
    def test_matches_duplicates_but_not_different_numbers(self):
        records = [{"question": q} for q in ("What is 12 plus 34?", "What is 12 plus 43?", "What is 12 plus 34?")]
        near = nearest_prior(records)
        self.assertEqual(near[1], (-1, 0.0))        # different numbers: no candidate at all
        self.assertEqual(near[2][0], 0)              # exact repeat of the first question
        self.assertAlmostEqual(near[2][1], 1.0)


class SuccessTest(unittest.TestCase):
    def _record(self, latency: float) -> dict:
        call = {"tokens_in": 10, "tokens_out": 2, "latency_s": latency}
        return {"variant": "en", "question": "q", "answers": ["42"], "choices": [], "greedy_text": "42",
                "majority_text": "42", "large_text": "42", "calls": {"translit": [], "small": [call], "large": [call]}}

    def test_a_right_answer_past_the_latency_limit_is_not_a_success(self):
        cfg = load_config()
        cfg["floors"]["latency_limit_s"] = 5.0
        fast, slow = simulate([self._record(1.0), self._record(9.0)], cfg, "large")
        self.assertTrue(fast["correct"] and fast["success"])
        self.assertTrue(slow["correct"])
        self.assertFalse(slow["success"])

    def test_direct_items_skip_the_small_tier(self):
        cfg = load_config()
        record = self._record(1.0)
        escalated = simulate([record], cfg, "cascade", keep=[False])[0]
        direct = simulate([record], cfg, "cascade", keep=[False], direct=[True])[0]
        always_large = simulate([record], cfg, "large")[0]
        self.assertEqual(direct["cost"], always_large["cost"])
        self.assertGreater(escalated["cost"]["flops"], direct["cost"]["flops"])

    def test_split_sends_english_to_small_and_the_rest_to_large_with_the_rewrite(self):
        cfg = load_config()
        english = {**self._record(1.0), "detected_variant": "en"}
        arabizi = {**self._record(1.0), "detected_variant": "arabizi", "large_text": "wrong", "large_rescued_text": "42"}
        refused = {**english, "greedy_text": "عذرا، لا أستطيع المساعدة"}
        small, large, fallback = simulate([english, arabizi, refused], cfg, "split")
        self.assertEqual((small["tier"], large["tier"], fallback["tier"]), ("small", "large", "large"))
        self.assertTrue(large["correct"])      # the large model got the rewrite
        self.assertTrue(fallback["correct"])   # a refusal falls back to the large model
        self.assertGreater(fallback["cost"]["flops"], small["cost"]["flops"])

    def test_escalation_uses_the_rewrite_but_the_baseline_stays_raw(self):
        cfg = load_config()
        record = {**self._record(1.0), "large_text": "wrong", "large_rescued_text": "42"}
        self.assertFalse(simulate([record], cfg, "large")[0]["correct"])
        self.assertTrue(simulate([record], cfg, "cascade", keep=[False])[0]["correct"])
        self.assertTrue(simulate([record], cfg, "cascade", keep=[False], direct=[True])[0]["correct"])

    def test_variants_whose_savings_dont_pay_lose_their_threshold(self):
        cfg = load_config()
        call = {"tokens_in": 10, "tokens_out": 2, "latency_s": 1.0}
        record = {"calls": {"translit": [], "small": [call], "large": [call]}}
        record = {**record, "majority_correct": True}
        records = [{**record, "detected_variant": v} for v in ("en", "dialect") for _ in range(10)]
        # English keeps every item; dialect keeps 1 in 10, which can't cover the small tier's cost.
        scores = np.array([1.0] * 10 + [1.0] + [0.0] * 9)
        thresholds = {"per_variant": {"en": 0.5, "dialect": 0.5, "msa": None}}
        drop_unprofitable(thresholds, records, scores, cfg)
        self.assertEqual(thresholds["per_variant"], {"en": 0.5, "dialect": None, "msa": None})

    def test_a_variant_both_tiers_fail_on_cannot_stay_on_the_small_tier(self):
        cfg = load_config()
        call = {"tokens_in": 10, "tokens_out": 2, "latency_s": 1.0}
        record = {"calls": {"translit": [], "small": [call], "large": [call]}, "detected_variant": "arabizi",
                  "majority_correct": False, "large_correct": False}
        thresholds = {"per_variant": {"arabizi": 0.0}}
        drop_unprofitable(thresholds, [record] * 10, np.ones(10), cfg)
        self.assertIsNone(thresholds["per_variant"]["arabizi"])

    def test_loss_is_measured_against_escalating_with_the_rewrite(self):
        # The raw baseline fails too, but the rewritten escalation is right, so keeping this answer is a loss.
        record = {"majority_correct": False, "large_correct": False, "large_rescued_correct": True}
        self.assertEqual(losses_if_kept([record]).tolist(), [1.0])

    def test_cost_per_success_counts_failed_spend(self):
        outcomes = [{"success": True, "cost": {"tokens": 10}}, {"success": False, "cost": {"tokens": 30}}]
        self.assertEqual(cost_per_success(outcomes, "tokens"), 40)
        self.assertIsNone(cost_per_success(outcomes[1:], "tokens"))


class PipelineTest(unittest.TestCase):
    """Mock models only: checks the plumbing, not the method."""

    def test_end_to_end_without_rescue(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _config(tmp, 400, normalize=False, arabizi="none")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                pipeline.cmd_collect(cfg)
                pipeline.cmd_train(cfg)
                res = pipeline.cmd_evaluate(cfg)
            out = Path(tmp) / "default"
            for name in ("results.json", "results.md", "pareto.png", "variants.png", "cost_per_success.png", "router.pkl"):
                self.assertTrue((out / name).exists(), name)
            p = res["policies"]
            self.assertAlmostEqual(p["always_large"]["relative_cost_per_success"], 1.0)
            # Always-small is cheap per call, but its failures make each success cost more than its call price.
            small = p["always_small"]
            self.assertAlmostEqual(small["cost_per_success"], small["cost"]["flops"] / small["success_rate"])
            self.assertGreater(small["relative_cost_per_success"], small["relative_cost"])
            self.assertGreater(p["always_large"]["accuracy"], p["always_small"]["accuracy"])
            self.assertAlmostEqual(p["always_large"]["relative_cost"], 1.0)
            self.assertLess(p["halala"]["relative_cost"], 1.0)
            # The mock small model is worst at raw Arabizi, so Halala should escalate it more than English.
            h = p["halala"]["per_variant"]
            self.assertGreater(h["arabizi"]["escalation_rate"], h["en"]["escalation_rate"])
            # The synthetic questions are unique, so the cache must never fire on this set.
            self.assertEqual(p["halala_cache"]["cache_rate"], 0.0)

            readme = Path(tmp) / "README.md"
            readme.write_text("top\n<!-- results:start -->\nold\n<!-- results:end -->\nbottom\n", encoding="utf-8")
            inject_readme("NEW TABLE", readme=readme)
            self.assertEqual(readme.read_text(encoding="utf-8"),
                             "top\n<!-- results:start -->\nNEW TABLE\n<!-- results:end -->\nbottom\n")

    def test_model_rewrite_only_touches_arabizi(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _config(tmp, 40, arabizi="model")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                pipeline.cmd_collect(cfg, "train")
            with open(Path(tmp) / "default" / "collect_train.jsonl", encoding="utf-8") as f:
                records = [json.loads(line) for line in f]
            for r in records:
                rewritten = bool(r["calls"]["translit"])
                self.assertEqual(rewritten, r["variant"] == "arabizi", r["question"])


if __name__ == "__main__":
    unittest.main()
