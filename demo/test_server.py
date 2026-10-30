"""Tests for the demo server, on mock models only. Nothing here reaches a real model.

Run from anywhere: python demo/test_server.py
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import http.client
import json
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import build_examples
import server

from halala.collect import SYSTEM_ANSWER
from halala.config import load_config
from halala.models import Completion, OllamaModel

DEMO = Path(__file__).resolve().parent
ARABIZI = "wesh 3asmat el sa3odiya?"
ENGLISH = "What is the capital of Saudi Arabia?"
FORMAL = "ما هي عاصمة المملكة العربية السعودية؟"


class Spy:
    """A model that records what it is sent and answers from a script."""

    def __init__(self, name: str, reply: str = "Riyadh", delay: float = 0.0):
        self.name = name
        self.reply = reply
        self.delay = delay
        self.seen: list[tuple[str, str]] = []

    def complete(self, system, user, temperature=0.0, sample=0, hint=None) -> Completion:
        self.seen.append((system, user))
        time.sleep(self.delay)
        return Completion(self.reply, 10, 2, 0.5)


def steps(events: list[dict]) -> list[str]:
    return [event["step"] for event in events]


def rules_config() -> dict:
    cfg = load_config()
    cfg["cascade"]["arabizi"] = "rules"
    return cfg


class RouteTest(unittest.TestCase):
    def run_question(self, question, cfg=None, small=None, large=None, answers=(), paths=server.PATHS):
        self.small = small or Spy("small")
        self.large = large or Spy("large")
        return list(server.run_question(question, list(answers), paths, self.small, self.large, cfg or rules_config()))

    def test_english_goes_to_the_small_model_and_is_compared_with_the_large_one(self):
        events = self.run_question(ENGLISH)
        self.assertEqual(steps(events), ["form", "rewrite", "route", "asking", "answer", "spent", "asking", "direct", "done"])
        route = next(e for e in events if e["step"] == "route")
        self.assertEqual((route["route"], route["tier"]), ("small", "small"))
        self.assertEqual([text for _, text in self.small.seen], [ENGLISH])
        self.assertEqual([text for _, text in self.large.seen], [ENGLISH])
        direct = next(e for e in events if e["step"] == "direct")
        self.assertFalse(direct["same_call"])

    def test_arabizi_is_rewritten_with_no_model_call_and_the_raw_question_goes_direct(self):
        events = self.run_question(ARABIZI)
        rewrite = next(e for e in events if e["step"] == "rewrite")
        self.assertTrue(rewrite["rewritten"])
        self.assertEqual((rewrite["model_calls"], rewrite["tokens"]), (0, 0))
        self.assertEqual(self.small.seen, [])
        self.assertEqual([text for _, text in self.large.seen], [rewrite["prompt"], ARABIZI])

    def test_a_model_rewrite_is_reported_as_a_model_call(self):
        cfg = load_config()
        self.assertEqual(cfg["cascade"]["arabizi"], "model")
        small, large = server.live_models(cfg)
        events = list(server.run_question(ARABIZI, [], server.PATHS, small, large, cfg))
        rewrite = next(e for e in events if e["step"] == "rewrite")
        self.assertEqual(rewrite["model_calls"], 1)
        self.assertGreater(rewrite["tokens"], 0)
        spent = next(e for e in events if e["step"] == "spent")
        self.assertGreater(spent["tokens"], rewrite["tokens"])

    def test_the_same_call_is_not_made_twice(self):
        events = self.run_question(FORMAL)
        direct = next(e for e in events if e["step"] == "direct")
        self.assertTrue(direct["same_call"])
        self.assertEqual(len(self.large.seen), 1)
        self.assertEqual(steps(events).count("asking"), 1)

    def test_an_unusable_small_answer_falls_back_to_the_large_model(self):
        events = self.run_question(ENGLISH, small=Spy("small", reply=""))
        routes = [e["route"] for e in events if e["step"] == "route"]
        self.assertEqual(routes, ["small", "fallback"])
        spent = next(e for e in events if e["step"] == "spent")
        self.assertEqual(spent["tokens"], 24)   # both calls are paid for
        self.assertTrue(next(e for e in events if e["step"] == "direct")["same_call"])
        self.assertEqual(len(self.large.seen), 1)

    def test_every_call_uses_the_pipeline_instruction(self):
        self.run_question(ENGLISH)
        self.assertEqual({system for system, _ in self.small.seen + self.large.seen}, {SYSTEM_ANSWER})
        with mock.patch.object(server, "SYSTEM_ANSWER", "A later instruction."):
            self.run_question(ENGLISH)
        self.assertEqual({system for system, _ in self.small.seen + self.large.seen}, {"A later instruction."})

    def test_answers_are_only_marked_when_there_is_an_answer_key(self):
        typed = self.run_question(ARABIZI)
        self.assertIsNone(next(e for e in typed if e["step"] == "answer")["correct"])
        keyed = self.run_question(ARABIZI, large=Spy("large", reply="Jeddah"), answers=["Riyadh"])
        self.assertIs(next(e for e in keyed if e["step"] == "answer")["correct"], False)

    def test_paths_run_one_side_only(self):
        self.assertEqual(steps(self.run_question(ARABIZI, paths=["direct"])), ["asking", "direct", "done"])
        self.assertNotIn("direct", steps(self.run_question(ARABIZI, paths=["halala"])))


class NoCacheTest(unittest.TestCase):
    def test_a_repeated_question_is_a_new_call_and_nothing_is_left_behind(self):
        cfg = load_config()
        for tier in server.TIERS:
            cfg["models"][tier].update(backend="ollama", name=f"not-called-{tier}")
        before = set(DEMO.iterdir())
        calls = []

        def fake_call(model, system, user, temperature, sample, hint):
            calls.append(user)
            return Completion("Riyadh", 10, 2, 0.5)

        with mock.patch.object(OllamaModel, "_call", fake_call):
            small, large = server.live_models(cfg)
            self.assertIsNone(small.cache)
            self.assertIsNone(large.cache)
            small.complete(SYSTEM_ANSWER, ENGLISH)
            small.complete(SYSTEM_ANSWER, ENGLISH)
        self.assertEqual(calls, [ENGLISH, ENGLISH])
        self.assertEqual(set(DEMO.iterdir()), before)


class ServerCase(unittest.TestCase):
    cfg = staticmethod(rules_config)

    def setUp(self):
        self.server = server.make_server(self.cfg(), 0)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(connection.close)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.read()

    def ask(self, payload):
        headers = {"Content-Type": "application/json"}
        return self.request("POST", "/api/ask", json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers)


class HttpTest(ServerCase):
    def test_serves_the_page_and_its_data_only(self):
        for path in ("/", "/index.html", "/numbers.js", "/examples.js"):
            self.assertEqual(self.request("GET", path)[0], 200, path)
        for path in ("/server.py", "/comparisons.json", "/../configs/default.toml", "/..%2fconfigs%2fdefault.toml"):
            self.assertEqual(self.request("GET", path)[0], 404, path)

    def test_status_says_mock_and_gives_the_pipeline_instruction(self):
        code, body = self.request("GET", "/api/status")
        status = json.loads(body)
        self.assertEqual(code, 200)
        self.assertTrue(status["mock"])
        self.assertEqual(status["instruction"], SYSTEM_ANSWER)
        self.assertEqual(status["models"]["large"]["name"], "mock-large")

    def test_ask_streams_events(self):
        code, body = self.ask({"question": ARABIZI})
        self.assertEqual(code, 200)
        events = [json.loads(line) for line in body.decode("utf-8").splitlines()]
        self.assertEqual(events[0], {"step": "form", "form": "arabizi"})
        self.assertEqual(events[-1], {"step": "done"})

    def test_bad_requests_are_refused(self):
        for payload in ({"question": ""}, {"question": "x" * (server.MAX_QUESTION + 1)}, {"question": "a", "paths": ["x"]}):
            self.assertEqual(self.ask(payload)[0], 400, payload)
        json_only = {"Content-Type": "text/plain"}
        self.assertEqual(self.request("POST", "/api/ask", b'{"question": "a"}', json_only)[0], 415)
        self.assertEqual(self.request("POST", "/api/ask", b"{", {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request("POST", "/api/nope", b"{}", {"Content-Type": "application/json"})[0], 404)

    def test_a_second_server_cannot_take_the_same_port(self):
        with self.assertRaises(OSError):
            server.make_server(self.cfg(), self.port)

    def test_other_hosts_are_refused(self):
        self.assertEqual(self.request("GET", "/api/status", headers={"Host": "attacker.example"})[0], 403)

    def test_a_model_failure_reaches_the_page_and_the_server_keeps_going(self):
        def fail(*args, **kwargs):
            raise OSError("model is down")

        with mock.patch.object(self.server.demo.large, "complete", fail), mock.patch("traceback.print_exc"):
            code, body = self.ask({"question": ARABIZI})
        events = [json.loads(line) for line in body.decode("utf-8").splitlines()]
        self.assertEqual(code, 200)
        self.assertEqual(events[-1]["step"], "error")
        self.assertIn("model is down", events[-1]["message"])
        self.assertEqual(self.ask({"question": ARABIZI})[0], 200)

    def test_each_step_arrives_before_the_slow_call_finishes(self):
        self.server.demo.large = Spy("large", delay=0.5)
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        self.addCleanup(connection.close)
        connection.request("POST", "/api/ask", json.dumps({"question": ARABIZI, "paths": ["halala"]}),
                           {"Content-Type": "application/json"})
        response = connection.getresponse()
        arrivals = {}
        start = time.perf_counter()
        for line in response:
            arrivals[json.loads(line)["step"]] = time.perf_counter() - start
        self.assertLess(arrivals["asking"], 0.25)
        self.assertGreater(arrivals["answer"], 0.4)


class ReplayTest(unittest.TestCase):
    def test_recorded_runs_have_the_same_shape_as_live_runs(self):
        cfg = rules_config()
        small, large = server.live_models(cfg)
        live = {}
        for question in (ARABIZI, ENGLISH, FORMAL):
            for event in server.run_question(question, ["Riyadh"], server.PATHS, small, large, cfg):
                live.setdefault(event["step"], set(event))
        text = (DEMO / "examples.js").read_text(encoding="utf-8")
        data = json.loads(text.split("=", 1)[1].rsplit(";", 1)[0])
        sides = [s for c in data["comparisons"] for e in c["examples"] for s in (e["left"], e["right"])] + data["picks"]
        self.assertTrue(sides)
        for side in sides:
            for event in side["events"]:
                self.assertEqual(set(event), live[event["step"]], event["step"])

    def test_examples_stay_data(self):
        spec = {"comparisons": [{"id": "other", "left": {"form": "msa"}, "right": {"form": "najdi"}, "fix": None,
                                 "examples": [{"group": "sa-001", "label": "Capital city"}]}],
                "picks": []}
        run = DEMO.parent / build_examples.RUN
        cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
        data = build_examples.build(spec, cfg, build_examples.load_records(run))
        example = data["comparisons"][0]["examples"][0]
        self.assertEqual((example["left"]["form"], example["right"]["form"]), ("msa", "najdi"))
        self.assertEqual(example["glosses"], {})


if __name__ == "__main__":
    unittest.main()
