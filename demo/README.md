# Halala demo

The working prototype for the video. `PLAN.md` describes what it should show.

`server.py` runs the real Halala path and streams each step to the page, using `steps` from `halala/pipeline.py`. `index.html` is a
placeholder until the console is built.

```bash
python demo/server.py --config configs/local_gemma.toml
```

Then open `http://127.0.0.1:8770/`. To try it without a GPU, use `--config configs/default.toml`, which runs mock models.

Tests use mock models only:

```bash
python demo/test_server.py
```
