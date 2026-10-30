"""Predicts whether the small model's majority answer is right, from cheap signals only."""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np

from .features import QUESTION_FEATURES

SAMPLE_SIGNALS = ("agreement", "n_distinct", "greedy_in_majority", "answer_len", "rewrite_rejected")
FEATURE_NAMES = QUESTION_FEATURES + SAMPLE_SIGNALS


def vectorize(records: list[dict]) -> np.ndarray:
    rows = []
    for r in records:
        f = r["features"]
        rows.append([f[name] for name in QUESTION_FEATURES] + [
            r["agreement"], r["n_distinct"], float(r["greedy_in_majority"]), len(r["majority_text"]),
            float(r.get("rewrite_rejected", False)),
        ])
    return np.asarray(rows, dtype=float)


class Router:
    """kind: hgb | xgboost | logreg (learned), or agreement (the sample agreement rate, no learning)."""

    def __init__(self, kind: str = "hgb", seed: int = 13):
        self.kind, self.seed = kind, seed
        self.model = None
        self.constant: float | None = None

    def _make(self):
        if self.kind == "hgb":
            from sklearn.ensemble import HistGradientBoostingClassifier
            return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.1, max_iter=200, random_state=self.seed)
        if self.kind == "xgboost":
            from xgboost import XGBClassifier
            return XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.1, subsample=0.9,
                                 eval_metric="logloss", random_state=self.seed)
        if self.kind == "logreg":
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
            return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
        raise ValueError(f"unknown router model: {self.kind}")

    def fit(self, records: list[dict]) -> "Router":
        if self.kind == "agreement":
            return self
        y = np.array([r["majority_correct"] for r in records], dtype=int)
        if len(np.unique(y)) < 2:
            self.constant = float(y.mean()) if len(y) else 0.0
            return self
        self.model = self._make()
        self.model.fit(vectorize(records), y)
        return self

    def score(self, records: list[dict]) -> np.ndarray:
        """Estimated probability that the small model's majority answer is correct."""
        if self.kind == "agreement":
            return np.array([r["agreement"] for r in records], dtype=float)
        if self.constant is not None:
            return np.full(len(records), self.constant)
        if not records:
            return np.zeros(0)
        return self.model.predict_proba(vectorize(records))[:, 1]

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @staticmethod
    def load(path: Path) -> "Router":
        with open(path, "rb") as f:
            return pickle.load(f)
