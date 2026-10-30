# Halala

Serve Arabic-first answers with a fraction of the compute, without any dialect paying for the savings.

> **Status:** hackathon skeleton. The pipeline runs end to end on mock models; real results come from real
> models at the event. The build plan is in [PLAN.md](PLAN.md).

## The problem

The cheap way to serve an LLM is to let a small model answer the easy questions and send only the hard ones to
the big model. But a router tuned on formal Arabic treats Najdi, Arabizi and mixed Arabic-English questions as
easy too, sends them to the small model, and they fail quietly. Formal-Arabic users get the savings; everyday
Saudi users get the worse answers.

## How Halala works

1. **Cheap cleanup:** strip diacritics and tatweel, convert Arabic-Indic digits, and rewrite Arabizi in Arabic
   script, so the small model can handle more of the dialect traffic.
2. **Small model, sampled k times:** sample 0 is greedy, the rest add a self-consistency signal.
3. **Router:** a gradient-boosted classifier predicts whether the small model's majority answer is right, from
   cheap signals only (script, Arabizi and dialect cues, sample agreement).
4. **Per-variant thresholds:** each detected variant (English, MSA, dialect, Arabizi, mixed) gets its own
   threshold. Each one is certified on a calibration split with a binomial test, so that variant's accuracy loss
   compared with always using the large model stays under ε with probability at least 1 − δ. A variant with too
   little calibration data always escalates.
5. **Escalate** to the large model when the router's score is below that variant's threshold. The large model
   always sees the raw question.

Every model call is cached in `cache/calls.sqlite`. Each routing policy is replayed offline from one collection
pass, so ablations and threshold sweeps cost nothing and rerun identically.

## Quick start

```bash
python -m pip install -r requirements.txt
python -m halala smoke
python -m unittest
```

`smoke` builds a synthetic parallel dataset and runs the whole pipeline on mock models in seconds.

## Commands

| Command | What it does |
|---|---|
| `python -m halala collect --config C [--split S]` | Both tiers answer every item once; all calls cached |
| `python -m halala train --config C` | Fit the router on `train`, certify thresholds on `calib` |
| `python -m halala evaluate --config C [--readme]` | Replay every policy on `test`; write table and charts |
| `python -m halala run --config C [--readme]` | `collect`, `train` and `evaluate` in one go |
| `python -m halala tokens --config C` | Token-tax baseline: input tokens per variant vs English |
| `python -m halala ask --config C "question"` | One question through the live cascade, with a trace |
| `python -m halala compare --configs A B ...` | Ablation table across runs |
| `python -m halala check --config C [--save]` | Regression gate against the saved baseline |
| `python -m halala profile --config C [--split S]` | Per-variant accuracy and agreement; a page to read every answer |
| `python -m halala review --data F` | Render a dataset as a page to check by hand, flagging mislabelled rows |
| `python -m halala seal --data F` | Split your questions into a dev file and a sealed test file |
| `python -m halala collect --config C --split sealed --unseal` | The final run on the sealed test set; each opening is logged |
| `python -m halala evaluate --config C --split sealed` | Report on the sealed test set (written to `runs/<config>/sealed/`) |
| `python -m halala convert-mcq --csv F --out O` | Multiple-choice CSV (e.g. ArabicMMLU) to Halala JSONL |
| `python -m halala synth --groups N` | Write the synthetic arithmetic set |

Configs in `configs/` are layered over `configs/default.toml`: `no_rescue.toml` (ablation), `ollama.toml`
(local models), `api.toml` (any OpenAI-compatible endpoint; the key comes from an environment variable),
`api_ollama.toml` (the same backend tested against Ollama's `/v1` endpoint), `allam.toml` and
`allam_profile.toml` (ALLaM 7B locally).

## Data formats

One JSON object per line. Short answer: `{"id", "group_id", "variant", "question", "answers": [aliases]}`.
Multiple choice adds `"choices": [options in order]` and puts the correct letter in `"answers": ["B"]`.
Items sharing a `group_id` are the same question in different variants and always land in the same split.

Rewrite examples for the Arabizi step (H5) are `{"arabizi", "arabic"}` pairs; set `[cascade] arabizi_examples`.
`data/arabizi_examples.template.jsonl` only shows the format: write your own, checked by a native speaker.
Runs stop if an example matches a question in the data, since that would leak answers.

## The sealed test set

`seal` splits whole question groups into `<name>.dev.jsonl`, which you work on, and
`data/sealed/<name>.test.jsonl`, which you leave alone until the final evaluation. The manifest next to it
records the file's SHA-256 and every time it was opened. Runs stop if the working data overlaps the sealed
set, if the sealed file changed since sealing, or if `--split sealed` is used without `--unseal`.

## Layout

```
halala/
  normalize.py   Arabic cleanup and rule-based Arabizi transliteration
  features.py    script, Arabizi and dialect cues; variant detection
  models.py      mock, Ollama and OpenAI-compatible backends; the call cache
  collect.py     one pass: rewrite, small samples, large answer, everything saved
  router.py      predicts whether the small answer is right
  calibrate.py   binomial fixed-sequence test for per-variant thresholds
  policies.py    offline replay of every policy, costs and metrics
  report.py      tables, charts, README results, comparison, regression gate
  pipeline.py    the commands
data/            smoke_parallel.jsonl (hand-written), synthetic_arith.jsonl (generated)
runs/<config>/   collected records, router, thresholds, results, charts
```

## Results

<!-- results:start -->
_No results yet. Run `python -m halala evaluate --config <file> --readme`._
<!-- results:end -->
