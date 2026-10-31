# Halala

Every AI answer costs compute, right or wrong, so the real price is the cost of a correct answer. That price depends on how you
write, and average scores hide it. That's the Dialect Tax.

Halala is a thin layer in front of the model. It measures the tax for each way of writing, removes what it can before the model
runs, and moves to the next leak. `PLAN.md` has the full plan and the checklist.

## Run it

```bash
pip install -r requirements.txt
python -m unittest
```

The tests use mock models. For real answers, install [Ollama](https://ollama.com), pull `gemma3:4b`, pull the community build
`hf.co/Omartificial-Intelligence-Space/ALLaM-7B-Instruct-preview-Q4_K_M-GGUF:Q4_K_M`, copy it to `allam-7b-q4` with `ollama cp`, and
build `allam-7b-q4-inst` from `configs/allam.Modelfile`. Then use these commands, each with `--config configs/local_gemma.toml`:

| Command | What it does |
|---|---|
| `python -m halala ask "wesh 3asmat el sa3odiya?"` | Sends one question through Halala and prints each step |
| `python -m halala dialect-tax` | Tokens and real seconds per correct answer by form, with and without Halala |
| `python -m halala fresh --data data/arabizi_fresh3.jsonl` | Arabizi on questions nobody tuned on, against the same questions in proper Arabic |
| `python -m halala check` | Fails if a form falls two or more correct answers below the saved baseline |
| `python -m halala measure` | ALLaM alone against Halala on mixed traffic |
| `python -m halala dialect-audit` | The tax on a public benchmark, in 7 forms, on both models |
| `python -m halala scorecard --models <names>` | The same audit across any models you have, to compare their Dialect Tax |
| `python -m halala sealed --unseal` | The one run on the sealed test set, which is logged |

`python demo/server.py --config configs/local_gemma.toml` starts the demo.

## What's where

| Path | What it holds |
|---|---|
| `halala/pipeline.py` | Halala itself: the one path its answers take, in the commands and the demo |
| `halala/normalize.py`, `arabizi_lexicon.py`, `spelling.py` | Cleanup and the Arabizi rewrite, with no model call |
| `halala/features.py` | Detecting how a question was written |
| `halala/measure.py`, `dialect_audit.py` | Measuring the tax |
| `data/` | Development questions, the sealed test set and the public benchmark sample |
| `runs/` | Results, including what didn't work |
| `cache/calls.sqlite` | Saved model calls, which `sealed` and the audits replay |

## Credits

`data/arabic_words.txt` merges two public word-frequency lists, and it's shared under CC BY-SA 4.0: subtitles from
[hermitdave/FrequencyWords](https://github.com/hermitdave/FrequencyWords) (CC BY-SA 4.0) and Arabic Wikipedia from
[IlyaSemenov/wikipedia-word-frequency](https://github.com/IlyaSemenov/wikipedia-word-frequency).
