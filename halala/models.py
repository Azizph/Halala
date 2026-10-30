"""Model backends with token and latency accounting, plus a persistent call cache."""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import resolve
from .features import ARABIC_LETTER, detect_variant
from .normalize import arabizi_to_arabic


@dataclass
class Completion:
    text: str
    tokens_in: int
    tokens_out: int
    latency_s: float


class CallCache:
    """Every real model call, keyed by its inputs. Reruns and ablations replay instead of paying again.
    Commit this file at the end of the event and anyone can reproduce your numbers without API access."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self._lock = threading.Lock()

    def get(self, key: str) -> Completion | None:
        with self._lock:
            row = self._db.execute("SELECT value FROM calls WHERE key = ?", (key,)).fetchone()
        return Completion(**json.loads(row[0])) if row else None

    def put(self, key: str, completion: Completion) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO calls VALUES (?, ?)",
                (key, json.dumps(asdict(completion), ensure_ascii=False)),
            )
            self._db.commit()

    def close(self) -> None:
        self._db.close()


class Model:
    def __init__(self, cfg: dict, cache: CallCache | None = None):
        self.cfg = cfg
        self.name = cfg["name"]
        self.params_b = float(cfg.get("params_b", 0))
        self.max_tokens = int(cfg.get("max_tokens", 64))
        self.cache = cache

    def complete(self, system: str, user: str, temperature: float = 0.0, sample: int = 0,
                 hint: dict | None = None) -> Completion:
        """`hint` carries ground truth for the mock backend only; real backends ignore it."""
        key = None
        if self.cache is not None:
            parts = [self.cfg["backend"], self.name, system, user, temperature, sample, self.max_tokens]
            key = hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()
            hit = self.cache.get(key)
            if hit is not None:
                return hit
        out = self._call(system, user, temperature, sample, hint or {})
        if key is not None:
            self.cache.put(key, out)
        return out

    def _call(self, system: str, user: str, temperature: float, sample: int, hint: dict) -> Completion:
        raise NotImplementedError


def _mock_tokens(text: str) -> int:
    # Crude stand-in for tokenizer fertility: Arabic letters cost more tokens than Latin ones.
    n_ar = len(ARABIC_LETTER.findall(text))
    return max(1, math.ceil(n_ar / 2.5 + (len(text) - n_ar) / 4))


class MockModel(Model):
    """Deterministic stand-in so the whole pipeline runs with no model. Its numbers are not evidence."""

    def _call(self, system, user, temperature, sample, hint):
        if hint.get("task") == "transliterate":
            text = arabizi_to_arabic(user)
        else:
            accuracy = float(self.cfg.get("mock_accuracy", {}).get(detect_variant(user), 0.5))
            gold = str(hint.get("answer", ""))
            draw = "greedy" if temperature == 0 else sample
            rng = random.Random(f"{self.name}|{user}|{draw}")
            if rng.random() < accuracy:
                text = gold
            elif gold.lstrip("-").isdigit():
                text = str(int(gold) + rng.choice([-10, -2, -1, 1, 2, 10]))
            else:
                text = "لا أعرف"
        t_in, t_out = _mock_tokens(system + user), _mock_tokens(text)
        return Completion(text, t_in, t_out, latency_s=round(self.params_b * (t_in + t_out) * 2e-4, 6))


class OllamaModel(Model):
    def _call(self, system, user, temperature, sample, hint):
        host = self.cfg.get("host", "http://localhost:11434").rstrip("/")
        body = {
            "model": self.name,
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": temperature, "seed": sample, "num_predict": self.max_tokens},
        }
        if "think" in self.cfg:   # reasoning models spend the token limit on thinking unless this is off
            body["think"] = self.cfg["think"]
        import requests

        start = time.perf_counter()
        r = requests.post(f"{host}/api/chat", json=body, timeout=300)
        r.raise_for_status()
        data = r.json()
        # prompt_eval_count can drop when Ollama reuses its prompt cache; note that when comparing runs.
        return Completion(
            data["message"]["content"].strip(),
            int(data.get("prompt_eval_count", 0)),
            int(data.get("eval_count", 0)),
            time.perf_counter() - start,
        )


class OpenAIModel(Model):
    """Any OpenAI-compatible /chat/completions endpoint."""

    def _call(self, system, user, temperature, sample, hint):
        base = self.cfg["base_url"].rstrip("/")
        key = os.environ.get(self.cfg.get("api_key_env", "HALALA_API_KEY"), "")
        body = {
            "model": self.name,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        if self.cfg.get("send_seed", True):
            body["seed"] = sample
        import requests

        start = time.perf_counter()
        r = requests.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                          json=body, timeout=300)
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage") or {}
        return Completion(
            (data["choices"][0]["message"]["content"] or "").strip(),
            int(usage.get("prompt_tokens", 0)),
            int(usage.get("completion_tokens", 0)),
            time.perf_counter() - start,
        )


BACKENDS = {"mock": MockModel, "ollama": OllamaModel, "openai": OpenAIModel}


def build_models(cfg: dict) -> tuple[Model, Model, CallCache | None]:
    specs = cfg["models"]
    real = [specs[tier]["backend"] != "mock" for tier in ("small", "large")]
    cache = CallCache(resolve(cfg["run"]["cache_path"])) if any(real) else None
    small, large = (
        BACKENDS[specs[tier]["backend"]](specs[tier], cache if is_real else None)
        for tier, is_real in zip(("small", "large"), real)
    )
    return small, large, cache
