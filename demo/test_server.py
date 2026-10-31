"""Tests for the demo server, on mock models and saved calls. Nothing here reaches a real model.

Run from anywhere: python demo/test_server.py
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import http.client
import json
import re
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import server

from halala.config import load_config, resolve
from halala.dialect_audit import FORMS, ask_item
from halala.models import Completion, OllamaModel, build_models
from halala.pipeline import SYSTEM_ANSWER, SYSTEM_MC, format_mc

DEMO = Path(__file__).resolve().parent
SHOWN_MODELS = {"allam-7b-q4-inst": "ALLaM 7B", "gemma3:4b": "Gemma 3 4B", "qwen2.5:7b": "Qwen 2.5 7B", "qwen2.5:1.5b": "Qwen 2.5 1.5B"}
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


class RouteTest(unittest.TestCase):
    def run_question(self, question, cfg=None, small=None, large=None, answers=(), paths=server.PATHS):
        self.small = small or Spy("small")
        self.large = large or Spy("large")
        return list(server.run_question(question, list(answers), paths, self.small, self.large, cfg or load_config()))

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
        self.assertEqual(self.small.seen, [])
        self.assertEqual([text for _, text in self.large.seen], [rewrite["prompt"], ARABIZI])

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
    cfg = staticmethod(load_config)

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
        for path in ("/", "/index.html"):
            self.assertEqual(self.request("GET", path)[0], 200, path)
        for path in ("/server.py", "/../configs/default.toml", "/..%2fconfigs%2fdefault.toml"):
            self.assertEqual(self.request("GET", path)[0], 404, path)

    def test_status_says_mock_and_gives_the_pipeline_instruction(self):
        code, body = self.request("GET", "/api/status")
        status = json.loads(body)
        self.assertEqual(code, 200)
        self.assertTrue(status["mock"])
        self.assertEqual(status["instruction"], SYSTEM_ANSWER)
        self.assertEqual(status["models"]["large"], "mock-large")

    def test_questions_carry_their_answers_for_the_receipts(self):
        code, body = self.request("GET", "/api/questions")
        questions = json.loads(body)["questions"]
        self.assertEqual(code, 200)
        self.assertEqual(len(questions), 40)
        self.assertEqual(set(questions[0]), {"id", "group", "form", "question", "answers"})

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

    def test_the_benchmark_comes_with_every_form_and_never_the_sealed_set(self):
        code, body = self.request("GET", "/api/benchmark")
        groups = json.loads(body)["groups"]
        self.assertEqual(code, 200)
        self.assertEqual(len(groups), 100)
        self.assertTrue(all([f["form"] for f in g["forms"]] == list(FORMS) for g in groups))
        self.assertTrue(all(g["group"].startswith("dmmlu-") for g in groups))

    def test_every_dialect_asks_each_form_straight_and_marks_the_reply(self):
        group, items = next(iter(self.server.demo.groups.items()))
        key = items[0].answers[0]
        for reply, right in ((key, True), ("ABCD"[("ABCD".index(key) + 1) % 4], False)):
            self.server.demo.large = spy = Spy("large", reply=reply)
            self.server.demo.last_call = time.monotonic()   # no pause, so no warm-up
            code, body = self.request("POST", "/api/every-dialect", json.dumps({"group": group}), {"Content-Type": "application/json"})
            events = [json.loads(line) for line in body.decode("utf-8").splitlines()]
            replies = [e for e in events if e["step"] == "reply"]
            self.assertEqual(code, 200)
            self.assertEqual([r["form"] for r in replies], list(FORMS))
            self.assertEqual(events[-1], {"step": "done"})
            self.assertEqual(spy.seen, [(SYSTEM_MC, format_mc(it.question, it.choices)) for it in items])
            self.assertEqual({r["picked"] for r in replies}, {reply})
            self.assertEqual({r["correct"] for r in replies}, {right})
            self.assertEqual({r["tokens"] for r in replies}, {12})

    def test_every_dialect_refuses_anything_but_a_benchmark_question(self):
        headers = {"Content-Type": "application/json"}
        for raw in (b"{", b"[]", b"{}", b'{"group": "nope"}', b'{"group": ["a"]}'):
            self.assertEqual(self.request("POST", "/api/every-dialect", raw, headers)[0], 400, raw)

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

    def test_a_pause_warms_the_model_before_the_question(self):
        self.server.demo.large = spy = Spy("large")
        self.assertEqual(self.ask({"question": FORMAL})[0], 200)
        self.assertEqual(len(spy.seen), 2)   # the warm-up, then the question
        self.assertEqual(self.ask({"question": ENGLISH, "paths": ["direct"]})[0], 200)
        self.assertEqual(len(spy.seen), 3)   # no pause, so no warm-up

    def test_each_step_arrives_before_the_slow_call_finishes(self):
        self.server.demo.large = Spy("large", delay=0.5)
        self.server.demo.last_call = time.monotonic()   # no pause, so no warm-up
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


class TypedNumbersTest(unittest.TestCase):
    """The Dialects tab types its saved numbers in, so they are checked against where they came from."""

    page = (DEMO / "index.html").read_text(encoding="utf-8")

    def scorecard_rows(self) -> dict[str, list[list[str]]]:
        rows: dict[str, list[list[str]]] = {}
        for row in (DEMO.parent / "runs/local_gemma/scorecard.md").read_text(encoding="utf-8").splitlines():
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            if len(cells) == 8 and cells[0] in SHOWN_MODELS:
                rows.setdefault(cells[0], []).append(cells[1:])
        return rows

    def test_the_scorecard_on_the_page_matches_the_saved_report(self):
        for name, (right, tax) in self.scorecard_rows().items():
            shown = f'{{ model: "{SHOWN_MODELS[name]}", right: [{", ".join(right)}], tax: [{", ".join(t.rstrip("x") for t in tax)}] }}'
            self.assertIn(shown, self.page)

    def test_the_picks_and_flips_on_the_page_replay_from_the_saved_calls(self):
        cfg = load_config(resolve("configs/local_gemma.toml"))
        with mock.patch.object(OllamaModel, "_call", side_effect=AssertionError("a real model call")):
            _, large, cache = build_models(cfg)
            self.addCleanup(cache.close)
            right = {group: {it.variant: ask_item(large, it)[1] for it in items}
                     for group, items in server.benchmark_groups().items()}
        self.assertEqual({form: sum(forms[form] for forms in right.values()) for form in FORMS},
                         dict(zip(FORMS, (58, 58, 46, 51, 53, 53, 54))))
        against = sum(forms["ENG"] and not forms["KSA"] for forms in right.values())
        back = sum(forms["KSA"] and not forms["ENG"] for forms in right.values())
        self.assertIn(f"againstSaudi: {against}, forSaudi: {back}", self.page)
        rule = [group for group, forms in right.items() if forms["ENG"] and forms["MSA"] and not forms["KSA"]]
        rule.remove("dmmlu-high_school_psychology-35")   # its statements I, II and III are missing from the benchmark
        picks = re.findall(r'\["(dmmlu-[^"]+)", "', self.page)
        self.assertEqual(picks, rule[:len(picks)])


if __name__ == "__main__":
    unittest.main()
