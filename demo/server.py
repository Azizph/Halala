"""Local server for the Halala demo: serves the page and runs the real Halala path on a question.

    python demo/server.py --config configs/local_gemma.toml

`run_question` follows `cmd_ask` in halala/pipeline.py with one event per step, so the page can show each step as it
happens. It leaves out the part of `cmd_ask` that writes ask.html into the run folder. Nothing here writes outside demo/.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True   # importing halala must not write into halala/__pycache__

import argparse
import copy
import json
import tempfile
import threading
import time
import traceback
from collections.abc import Iterator
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from halala.collect import SYSTEM_ANSWER, prepare_prompt
from halala.config import load_config, resolve
from halala.features import detect_variant
from halala.models import Model, build_models
from halala.policies import call_cost, usable_answer
from halala.scoring import score

DEFAULT_PORT = 8770   # index.html looks for the server here when it is opened from a file
PATHS = ("halala", "direct")
TIERS = ("small", "large")
MAX_QUESTION = 400
MAX_BODY = 8192
JS = "text/javascript; charset=utf-8"
PAGE_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/numbers.js": ("numbers.js", JS),
    "/examples.js": ("examples.js", JS),
}


def live_models(cfg: dict) -> tuple[Model, Model]:
    """The configured models with no call cache. A cached call replays its old seconds and tokens, and live mode has to
    show the call it just made. `build_models` opens a cache for real backends, so it gets a throwaway one in demo/."""
    live = copy.deepcopy(cfg)
    with tempfile.TemporaryDirectory(dir=HERE) as folder:
        live["run"]["cache_path"] = str(Path(folder) / "unused.sqlite")
        small, large, cache = build_models(live)
        if cache is not None:
            cache.close()
    small.cache = large.cache = None
    return small, large


def _ask(side: str, tier: str, model: Model, text: str, answers: list[str], cfg: dict) -> Iterator[dict]:
    """One model call, as `ask` makes it in `cmd_ask`. Announces the call first, because it can take seconds."""
    yield {"step": "asking", "side": side, "tier": tier, "model": model.name}
    c = model.complete(SYSTEM_ANSWER, text, 0.0, 0, {})
    return {
        "tier": tier,
        "model": model.name,
        "prompt": text,
        "text": c.text,
        "tokens_in": c.tokens_in,
        "tokens_out": c.tokens_out,
        "tokens": c.tokens_in + c.tokens_out,
        "seconds": c.latency_s,
        "compute": call_cost(asdict(c), cfg["models"][tier])["flops"],
        "correct": score(c.text, answers) if answers else None,
    }


def _route(route: str, tier: str, model: Model, cfg: dict) -> dict:
    return {"step": "route", "route": route, "tier": tier, "model": model.name,
            "params_b": cfg["models"][tier].get("params_b", 0)}


def _halala(question: str, answers: list[str], small: Model, large: Model, cfg: dict) -> Iterator[dict]:
    """The path through `cmd_ask`. Returns the call that produced the final answer."""
    variant = detect_variant(question)
    yield {"step": "form", "form": variant}

    start = time.perf_counter()
    prompt, rewrite_calls, rewrite = prepare_prompt(question, cfg["cascade"], small)
    seconds = time.perf_counter() - start
    tokens = sum(c["tokens_in"] + c["tokens_out"] for c in rewrite_calls)
    compute = sum(call_cost(c, cfg["models"]["small"])["flops"] for c in rewrite_calls)
    yield {"step": "rewrite", "rewritten": bool(rewrite.get("text")) and not rewrite.get("rejected"),
           "rejected": rewrite.get("rejected", ""), "prompt": prompt, "model_calls": len(rewrite_calls),
           "tokens": tokens, "seconds": seconds}

    calls = []
    if variant != "en":
        yield _route("large", "large", large, cfg)
        calls.append((yield from _ask("halala", "large", large, prompt, answers, cfg)))
        yield {"step": "answer", **calls[-1]}
    else:
        yield _route("small", "small", small, cfg)
        calls.append((yield from _ask("halala", "small", small, prompt, answers, cfg)))
        yield {"step": "answer", **calls[-1]}
        if not usable_answer(calls[-1]["text"]):
            yield _route("fallback", "large", large, cfg)
            calls.append((yield from _ask("halala", "large", large, question, answers, cfg)))
            yield {"step": "answer", **calls[-1]}

    yield {"step": "spent", "tokens": tokens + sum(c["tokens"] for c in calls),
           "seconds": seconds + sum(c["seconds"] for c in calls),
           "compute": compute + sum(c["compute"] for c in calls)}
    return calls[-1]


def run_question(question: str, answers: list[str], paths: tuple[str, ...] | list[str], small: Model, large: Model,
                 cfg: dict) -> Iterator[dict]:
    """Everything the page shows for one question, in the order it happens. `paths` picks Halala's route, the same raw
    question straight to the large model, or both. Halala goes first, so if Ollama's prompt cache shrinks the second
    call's token count, that counts against Halala rather than for it."""
    final = None
    if "halala" in paths:
        final = yield from _halala(question, answers, small, large, cfg)
    if "direct" in paths:
        if final is not None and final["tier"] == "large" and final["prompt"] == question:
            yield {"step": "direct", "same_call": True, **final}   # asking again would only repeat the call
        else:
            call = yield from _ask("direct", "large", large, question, answers, cfg)
            yield {"step": "direct", "same_call": False, **call}
    yield {"step": "done"}


class Demo:
    """What the request handlers share. One GPU, so one question at a time."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.small, self.large = live_models(cfg)
        self.lock = threading.Lock()

    def status(self) -> dict:
        models = self.cfg["models"]
        return {
            "config": self.cfg["run"]["name"],
            "mock": any(models[tier]["backend"] == "mock" for tier in TIERS),
            "models": {tier: {"name": models[tier]["name"], "params_b": models[tier].get("params_b", 0)}
                       for tier in TIERS},
            "instruction": SYSTEM_ANSWER,
            "rewrite": self.cfg["cascade"].get("arabizi", "none"),
        }

    def run(self, question: str, answers: list[str], paths: list[str]) -> Iterator[dict]:
        with self.lock:
            yield from run_question(question, answers, paths, self.small, self.large, self.cfg)


def read_request(raw: bytes) -> tuple[str, list[str], list[str]]:
    """The question, its answer key if the page knows one, and the paths to run. Raises ValueError if unusable."""
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError("expected a JSON object")
    question = str(body.get("question", "")).strip()
    if not question:
        raise ValueError("the question is empty")
    if len(question) > MAX_QUESTION:
        raise ValueError(f"the question is longer than {MAX_QUESTION} characters")
    answers = [str(a) for a in body.get("answers") or []]
    paths = [p for p in body.get("paths") or PATHS if p in PATHS]
    if not paths:
        raise ValueError("no known path to run")
    return question, answers, paths


class Handler(BaseHTTPRequestHandler):
    disable_nagle_algorithm = True   # each step should reach the page as soon as it happens

    def _from_this_machine(self) -> bool:
        port = self.server.server_port
        return self.headers.get("Host", "") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _send(self, code: int, kind: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, value: dict) -> None:
        self._send(code, "application/json; charset=utf-8", json.dumps(value, ensure_ascii=False).encode("utf-8"))

    def do_GET(self) -> None:
        if not self._from_this_machine():
            self._send_json(403, {"error": "this server only answers on this machine"})
            return
        path = urlsplit(self.path).path
        if path == "/api/status":
            self._send_json(200, self.server.demo.status())
        elif path in PAGE_FILES:
            name, kind = PAGE_FILES[path]
            self._send(200, kind, (HERE / name).read_bytes())
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._from_this_machine():
            self._send_json(403, {"error": "this server only answers on this machine"})
            return
        if urlsplit(self.path).path != "/api/ask":
            self._send_json(404, {"error": "not found"})
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"error": "send JSON"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            self._send_json(413, {"error": "the request is empty or too long"})
            return
        try:
            question, answers, paths = read_request(self.rfile.read(length))
        except ValueError as error:   # includes malformed JSON
            self._send_json(400, {"error": str(error)})
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            for event in self.server.demo.run(question, answers, paths):
                self._write_event(event)
        except ConnectionError:   # the page went away; requests' own errors are not this class
            pass
        except Exception as error:
            traceback.print_exc()
            self._write_event({"step": "error", "message": f"{type(error).__name__}: {error}"[:300]})

    def _write_event(self, event: dict) -> None:
        self.wfile.write(json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n")


class DemoServer(ThreadingHTTPServer):
    allow_reuse_address = False   # on Windows it would let a second server share the port and answer for the first


def make_server(cfg: dict, port: int) -> DemoServer:
    server = DemoServer(("127.0.0.1", port), Handler)
    server.demo = Demo(cfg)
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", required=True, help="TOML layered over configs/default.toml")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    cfg = load_config(resolve(args.config))
    try:
        server = make_server(cfg, args.port)
    except OSError as error:
        print(f"Can't use port {args.port}, is another demo server running? ({error})")
        return 1
    if server.demo.status()["mock"]:
        print("mock models: answers are placeholders. Use --config configs/local_gemma.toml for real ones.")
    print(f"Open http://127.0.0.1:{server.server_port}/   Ctrl+C stops the server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
