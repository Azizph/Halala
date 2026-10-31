"""Local server for the Halala demo: serves the page and runs the real Halala path on a question.

    python demo/server.py --config configs/local_gemma.toml

`run_question` streams `steps` from halala/pipeline.py, the same path the measurements use, so the page shows each step as
it happens. Nothing here writes outside demo/.
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

from halala.config import load_config, resolve
from halala.models import Model, build_models
from halala.pipeline import SYSTEM_ANSWER, load_dev, steps
from halala.scoring import score

DEFAULT_PORT = 8770
PAUSE_S = 2.0
PATHS = ("halala", "direct")
TIERS = ("small", "large")
MAX_QUESTION = 400
MAX_BODY = 8192
PAGE_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
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


def _marked(call: dict, answers: list[str]) -> dict:
    return {**call, "tokens": call["tokens_in"] + call["tokens_out"],
            "correct": score(call["text"], answers) if answers else None}


def _halala(question: str, answers: list[str], small: Model, large: Model, cfg: dict) -> Iterator[dict]:
    """Halala's path, event by event. Returns the call that produced the final answer."""
    calls = []
    for event in steps(question, small, large, cfg):
        if event["step"] == "answer":
            event = _marked(event, answers)
            calls.append(event)
        yield event
    yield {"step": "spent", "tokens": sum(c["tokens"] for c in calls), "seconds": sum(c["latency_s"] for c in calls),
           "active_s": sum(c["active_s"] for c in calls)}
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
            yield {**final, "step": "direct", "same_call": True}   # asking again would only repeat the call
        else:
            yield {"step": "asking", "tier": "large", "model": large.name}
            c = large.complete(SYSTEM_ANSWER, question, 0.0, 0, {})
            call = _marked({"tier": "large", "model": large.name, "prompt": question, **asdict(c)}, answers)
            yield {**call, "step": "direct", "same_call": False}
    yield {"step": "done"}


class Demo:
    """What the request handlers share. One GPU, so one question at a time."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.small, self.large = live_models(cfg)
        self.lock = threading.Lock()
        self.last_call = 0.0

    def warm_up(self) -> None:
        """Load the large model and its prompt first, so the first receipt isn't charged for them."""
        self.large.complete(SYSTEM_ANSWER, "مرحبا", 0.0, 0, {})

    def questions(self) -> list[dict]:
        """The development questions with their answers, for the picks and the traffic stream. Never the sealed ones."""
        return [{"id": it.id, "group": it.group_id, "form": it.variant, "question": it.question, "answers": it.answers}
                for it in load_dev(self.cfg)]

    def status(self) -> dict:
        models = self.cfg["models"]
        return {
            "config": self.cfg["run"]["name"],
            "mock": any(models[tier]["backend"] == "mock" for tier in TIERS),
            "models": {tier: models[tier]["name"] for tier in TIERS},
            "route_english": self.cfg["cascade"]["route_english"],
            "instruction": SYSTEM_ANSWER,
        }

    def run(self, question: str, answers: list[str], paths: list[str]) -> Iterator[dict]:
        with self.lock:
            if time.monotonic() - self.last_call > PAUSE_S:   # a first call after a pause runs ten times slower
                self.warm_up()                                # and that shouldn't land on either side of the receipt
            yield from run_question(question, answers, paths, self.small, self.large, self.cfg)
            self.last_call = time.monotonic()


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
        elif path == "/api/questions":
            self._send_json(200, {"questions": self.server.demo.questions()})
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
    server.demo.warm_up()
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
