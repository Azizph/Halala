# Halala demo

The working prototype for the hackathon video. `VIDEO_SCRIPT.md` is the shot list.

## Two modes

| Mode | When | Where answers come from | Label on screen |
|---|---|---|---|
| Live | `server.py` is running | Real model calls, made as you watch | Green `Live: ...` in the header, `Live` on each answer |
| Recorded | No server | Saved answers from the development run | `Recorded answers, no model running` in the header, `Recorded` on each answer |

The page uses live mode whenever it can reach the server. Double-clicking `index.html` while the server runs on its default
port goes to the live page. With no server it replays, and needs no network and no model. Record the video in live mode only.

The Live step shows each step as it happens: the form detected, the rewrite, the model chosen and why, the answer, and its
tokens and seconds. Beside it, the same raw question goes straight to the large model. If that would be the exact call Halala
just made, the page says so instead of asking twice.

## Run it

```bash
python demo/server.py --config configs/local_gemma.toml
```

Then open `http://127.0.0.1:8770/`. Add `--port` for another port, and open that address directly.

To try it without a GPU, use the mock models. The header turns red, and the answers are placeholders:

```bash
python demo/server.py --config configs/default.toml
```

`default.toml` rewrites Arabizi with a model, so step 3 reports a model call. `local_gemma.toml` uses the rules, so it reports
none. The page shows what really happened either way.

Live calls skip the call cache, because a cached call would replay old seconds and tokens. They aren't saved. Nothing the
server does writes outside `demo/`.

## Controls

| Key | Does |
|---|---|
| Right or Left arrow | Next or previous step |
| 1, 2, 3 | Switch example, on the steps that show one |
| N | Open or close the numbers |
| Esc | Close the numbers, or leave the question box |
| Home | Back to the start |

Everything is also clickable.

## Updating it

- **Numbers:** edit `numbers.js` only. Search for `PENDING`: Halala's row after prompt-eval, plus the sealed and audit
  sentences. The headline on the result step recalculates from Halala's cost.
- **Instruction:** it comes from `SYSTEM_ANSWER` in `halala/collect.py`, as it does for the pipeline, so a change there needs
  nothing here. First-sentence stopping is a `stop` list under `[models.*]`, so put it in the config the server starts with.
- **Recorded answers:** after a new collect run in `runs/local_gemma`, run `python demo/build_examples.py`.
- **Examples and picks:** edit `comparisons.json`, then run `python demo/build_examples.py`. It reads recorded runs only and
  calls no model. It stops if an example no longer shows what its comparison's `expect` says, or if the rewrite no longer
  matches the recorded run.
- **A new comparison:** add an entry to `comparisons` in `comparisons.json` and rebuild. No code changes. `left.form` and
  `right.form` name rows in `forms` in `numbers.js`. Add a row there if the form is new. `fix` names the row for the fixed form,
  or is `null` if there's no fix, and then the fix step drops out. Keep `heading` under about 38 characters.
- **A new form in live mode:** add what `detect_variant` returns to `detected` in `numbers.js`.

## Tests

Mock models only, so no GPU is needed:

```bash
python demo/test_server.py
```

## Check with a native speaker

- `هللة` in the header.
- The glosses in `comparisons.json`, which are hand translations. A gloss only shows when the reply matches exactly.
- The Vision 2030 example's rewrite really does contain a misspelling, `رءية` for `رؤية`. It's the rewrite's real output, and
  ALLaM still answered correctly, so it stays unless you drop the example.
