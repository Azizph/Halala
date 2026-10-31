# Halala demo

The working prototype for the video. `PLAN.md` describes what it should show.

`server.py` runs the real Halala path and streams each step to the page, using `steps` from `halala/pipeline.py`. `index.html` is
the console, with the traffic stream and the Dialects tab.

The Dialects tab asks one public benchmark question in seven forms through `ask_item` in `halala/dialect_audit.py`, the same call
the scorecard made. Those calls skip `steps` because Halala has no fix for dialects yet, and `for_model` would change the prompt.
A live reply can still differ from a saved one (`runs/local_gemma/live_replay.md`). The tab's scorecard, picks and flips are typed
into the page, and `test_server.py` checks them against `runs/local_gemma/scorecard.md` and the saved calls in `cache/calls.sqlite`.

```bash
python demo/server.py --config configs/local_gemma.toml
```

Then open `http://127.0.0.1:8770/`. To try it without a GPU, use `--config configs/default.toml`, which runs mock models.

Tests use mock models and saved calls, and never reach a real model:

```bash
python demo/test_server.py
```
