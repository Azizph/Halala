"""Load TOML configs layered over configs/default.toml."""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "configs" / "default.toml"


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | Path | None = None) -> dict:
    with open(DEFAULT_CONFIG, "rb") as f:
        cfg = tomllib.load(f)
    name = "default"
    if path is not None:
        path = Path(path)
        if path.resolve() != DEFAULT_CONFIG.resolve():
            with open(path, "rb") as f:
                cfg = _merge(cfg, tomllib.load(f))
        name = path.stem
    cfg["run"]["name"] = cfg["run"].get("name") or name
    return cfg


def resolve(path: str | Path) -> Path:
    """Paths in configs are relative to the repo root unless absolute."""
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def run_dir(cfg: dict) -> Path:
    out = resolve(cfg["run"]["out_dir"]) / cfg["run"]["name"]
    out.mkdir(parents=True, exist_ok=True)
    return out
