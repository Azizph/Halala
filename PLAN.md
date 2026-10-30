# Halala: 48-hour build plan

**Pitch:** failed runs still burn compute, so the real price of AI is cost per successful task, and that price
isn't the same for everyone. Halala measures it per dialect, and brings it down without leaving any dialect behind.

**Design, decided 2026-10-30:** English goes to Gemma 3 4B once, and everything else goes to ALLaM 7B, with Arabizi
rewritten by rules and a word list first. The sampling, router and per-variant thresholds stay as a baseline
(`halala_full`), because they didn't earn their place. Config: `configs/local_gemma.toml`.

**What the dev data shows (ALLaM 7B Q4 with its correct prompt format, 45 questions per variant):** ALLaM gets 40 to
45 of 45 on English, formal Arabic, Najdi and mixed, and 9 of 45 on Arabizi as typed. So the story is narrow and fair:
ALLaM handles dialect well and has one measurable gap, and a rewrite with no model call takes Arabizi from 9 to 31.

## The challenge brief, point by point

Judges will read the project against these five points. Point 1 is what most teams will build, so lead with 4 and 5.

| Brief | What Halala does | Status |
|---|---|---|
| 1. Model choice per task | English to the small model, the rest to ALLaM | Built |
| 2. Context that earns its tokens | The Arabizi rewrite adds no prompt tokens; examples were measured and rejected on cost | Built |
| 3. Verification where it pays | Sampling was measured and dropped; the one check left is free (empty answer or refusal) | Built |
| 4. Cost per successful task | The headline metric: failed tasks count as spend, reported overall and per variant | Built |
| 5. Accuracy and latency floors | A task only succeeds if right and within the time limit; every variant must clear the floor; the guarantee bounds accuracy loss | Built |

## Positioning: why this isn't just another router

Many Challenge 2 teams will build a router. Treat the router as the part everyone has, and lead with three
things they won't have:

1. **A finding, not a tool.** Open with the measured failure: a standard cost-saving router sends dialect and
   Arabizi questions to the small model, and they come back wrong.
2. **An audit plus a fairness layer for any router.** "Everyone built a router. Halala is the test that shows
   whether yours is fair to dialect speakers, and the layer that makes it fair." `evaluate` already scores any
   policy per variant; run it on the standard one-threshold router (and another team's, if they'll share
   their outputs) to show the gap Halala exposes and closes.
3. **A dataset only a native speaker can make.** The same questions in English, MSA, Najdi, Arabizi and mixed,
   with every Najdi and Arabizi version written or checked by you. Release it with the submission.

## Findings so far

> **Correction, 2026-10-30: every ALLaM number before this note used the wrong prompt format.** Ollama fell back to a
> generic ChatML template (`<|im_start|>`), while ALLaM expects `[INST] <<SYS>> ... [/INST]` (its `tokenizer_config.json`).
> `configs/allam.Modelfile` fixes this, and the model is now `allam-7b-q4-inst`. Treat the older ALLaM entries below,
> including "20x", "3 of 45" and the Q4 vs Q8 comparison, as invalid until rerun. The old run is kept in
> `runs/local_chatml` as a comparison. Qwen comes from Ollama's library with its own template, so it's unaffected.

- **2026-10-29, one example, Ollama stand-ins (not ALLaM):** `wesh 3asmat el sa3odiya?` ("what's the capital
  of Saudi Arabia?"). qwen2.5:1.5b rewrote it to Arabic script as كم العشرين السعيد؟ ("how much is the happy
  twenty?"), so the meaning was lost before answering. Its five answers disagreed (agreement 0.2), so the router
  escalated, and qwen2.5:7b, given the raw Arabizi, answered "coastal fish". The code ran correctly; the models'
  Arabizi handling is what failed. One example is a lead, not a result: measure it on ALLaM at the event.
- **2026-10-30, three examples, ALLaM 7B Instruct (community Q8_0 GGUF, laptop):**
  - Najdi `وش عاصمة السعودية؟`: all five answers correct (الرياض, هي الرياض, مدينة الرياض...), but agreement
    scored 0.4 because voting compares exact wording, so it escalated for nothing. **Voting must group answers
    that say the same thing**, or the router throws away savings on chatty models.
  - Arabizi `wesh 3asmat el sa3odiya?`: ALLaM's rewrite gave عساكرة السعودية؟ ("Saudi soldiers"), and its
    answer to the raw Arabizi was nonsense. Same failure as Qwen, now on ALLaM. Still three examples, not a result.
  - Mixed `What's the عاصمة of السعودية?`: four of five correct; one claimed Saudi Arabia has no official capital.
  - About 40 to 80 seconds per question on this laptop, so full collections need Humain's API, not local runs.
- **2026-10-30, profile of ALLaM 7B (community Q8_0) on the 40 hand-written items, 8 per variant**
  (`runs/allam_profile/profile.md`). Majority-vote accuracy: English 100%, MSA 88%, Najdi 88%, mixed 88%,
  **Arabizi 12%**. On the raw Arabizi question (no rewrite) it got 0 of 8.
  - The rewrite rescued 1 of 8 Arabizi questions (the planet one) and turned most of the others into different
    questions: "how many days in a week" became "how old is the boy", "what's the currency" became a refusal, and
    "how many minutes in an hour" came out in Egyptian dialect ("الساعة كام دلوقتي؟", "what time is it now?").
  - The rewrite output sometimes isn't a rewrite: one was a refusal that then went to the model as the question;
    one answered the question and leaked a chat token (`<|im|>`). **Needs a check before use:** fall back to the
    raw question when the rewrite is a refusal, much longer than the input, or contains chat tokens.
  - Agreement is a usable but noisy signal: mean 0.60 to 0.93 when the majority was right, 0.37 to 0.60 when wrong.
  - Not only Arabizi: the Najdi and mixed versions of "15 plus 27" both came back 62, and the MSA planet question
    came back Saturn.
  - 8 items per variant is a strong lead, not a result. It makes H5 (rewrite with hand-written examples) the most
    promising experiment.
  - With the rewrite check added: it rejected exactly the two format failures (refusal, chat token); both fell
    back to the raw Arabizi, which ALLaM still got wrong, so Arabizi stays at 1 of 8. The check stops garbage
    being passed on; fixing meaning is H5's job. One fallback's majority answer was itself a refusal: the
    router should treat refusals like empty answers.
- **2026-10-30, tokens per correct answer on ALLaM 7B** (same 40 items; failed runs count as spend). English 80,
  MSA 89, Najdi 75, mixed 90. **Arabizi: no correct answers at all from the plain model**, and 1,628 tokens per correct
  answer with cleanup and rewrite, about 20x English. That figure rests on one correct answer out of 8, so one more
  would halve it. Use it as a lead, and report the full-set number instead.
- **2026-10-30, prompt trimming (H8)** (`runs/local_gemma/prompt_eval.md`, Halala's routing, 225 dev questions):

  | Instruction | Correct | Tokens per question | Cost per correct | Seconds per question |
  |---|---|---|---|---|
  | Current | 203 | 46.6 | 76% | 3.6 |
  | "Answer briefly." | 212 | 40.5 | 64% | 4.1 |
  | None | 213 | 40.3 | 58% | 5.4 |
  | None, first sentence only (estimated from saved answers, not run) | 209 | 30.8 | 47% | not measured |

  - Forcing answer-only replies hurt accuracy: Najdi 40 to 45, Arabizi 31 to 35 with no instruction. The 13 answers that
    flipped from wrong to right were read by hand and look truly right.
  - Longer answers ate most of the token saving (tokens out rose from 4.5 to 24.7), and time per question rose because output
    tokens are slower. The earlier claim of "roughly half" was too high without a limit on answer length.
- **2026-10-30, the simple design beats the full pipeline on cost, and needs no unverified assumption.** All 225 dev
  questions, estimated FLOPs, relative to always-ALLaM on the raw question (180 correct):

  | Design | Correct of 225 | Cost per correct |
  |---|---|---|
  | ALLaM + rewrite, no routing | 202 | 85% |
  | **English to Gemma 3 4B once, the rest ALLaM + rewrite** | **203** | **76%** |
  | English to Qwen 1.5B once, the rest ALLaM + rewrite | 197 | 72% |

  - The full pipeline (samples, classifier, thresholds) keeps only English on the small model anyway, with either model.
    On the 30 dev-test items it reaches 27 correct at 75 to 77%, but only if samples share a prompt pass. Without that
    unverified assumption it costs 86% (Qwen) or 94% (Gemma).
  - So the rewrite gives most of the gain, a language split gives the rest, and the classifier and thresholds add little at
    this data size. The savings estimate is FLOPs, not measured wall-clock time, and doesn't count model swaps.
  - **Gemma 3 4B dev run** (`runs/local_gemma`): one answer each, English 43, formal 36, Najdi 31, Arabizi 20, mixed 32 of 45.
    It reaches 80% at best (formal Arabic, 36 of 45) and calibration kept none of the Arabic forms on it, so it doesn't
    unlock savings there.
- **2026-10-30, Halala with the improved rewrite** (30 dev-test items, sealed set untouched): 27 correct vs 24 for
  always-ALLaM, at 75% of its cost per correct answer. Arabizi 4 of 6, and its cost per correct fell from 6.9x to 1.4x
  (English on always-large = 1.0x). Only English stays on Qwen. Arabizi still misses the 80% floor.
  - The first run with rules scored Arabizi 0 of 6, because calibration compared Qwen with raw-Arabizi ALLaM. Calibration now
    measures loss against escalating with the rewrite, and each variant's kept answers must clear the floor.
  - **Regression gate fired and was accepted:** cost vs always-large rose from 81% to 84% (a stricter English threshold), while
    cost per success fell from 78% to 75% and accuracy rose. Baseline re-saved on purpose.
  - These changes were made after looking at this split, so treat it as a dev result. The sealed set decides.
  - **The word list is likely overfitted.** It was written after seeing the dev questions, by someone who also wrote the sealed
    ones. 24 of 45 from general rules is the safer number; 31 includes the list. Test on fresh questions from the user.
  - **The scorer undercounts:** "SAR.", "برد" for cold and "إفرست" are right but missing from the aliases. Not fixed, because
    the sealed file is hashed and scoring must stay the same on both sets, so reported Arabizi numbers are conservative.
- **2026-10-30, Arabizi rewrite comparison (H5)** (`runs/rewrite_eval_final.md`, 45 dev Arabizi questions, ALLaM answers
  in every arm, cost per correct answer relative to the hand-checked Najdi upper bound):

  | Arm | Correct | Cost per correct |
  |---|---|---|
  | Raw Arabizi | 9 | 5.6x |
  | Original rules | 18 | 2.3x |
  | Improved rules, no word list | 24 | 1.8x |
  | **Improved rules + 125-word list, no model call** | **31** | **1.3x** |
  | Same, plus the raw text | 33 | 1.6x |
  | ArabiziKit, no model call | 15 | 2.9x |
  | ArabiziKit + ALLaM spelling fix | 10 | 11.8x |
  | Qwen rewrite | 4 | 14.3x |
  | Qwen rewrite + 16 examples | 6 | 22.5x |
  | ALLaM rewrite | 15 | 7.4x |
  | ALLaM rewrite + 16 examples | 26 | 17.5x |
  | ALLaM rewrite + 4 nearest examples | 22 | 9.1x |
  | Hand-checked Najdi (upper bound) | 40 | 1.0x |

  - **Examples raise accuracy but are expensive,** because they are re-sent on every call. Sending the nearest 4 kept most
    of the gain at about half the cost (brief point 2). The examples are drafts by Claude, not yet the user's.
  - **Rules are the default** (`[cascade] arabizi = "rules"`): most accurate of the affordable options, lowest cost per
    correct answer, no extra model call. Adding the raw text gained 2 questions (noise at this size) at higher cost.
  - **ArabiziKit reads standalone numbers as letters** ("15" -> "1خ"), so `normalize.arabizi_kit` keeps numbers away from it.
  - **No arm reaches the 80% floor (36 of 45).** The best is 33, and the upper bound is 40.
  - These are many comparisons on 45 questions, so small gaps mean little. 9 vs 31 is clear; 31 vs 33 is not.
- **2026-10-30, corrected dev run** (`configs/local.toml`, 225 dev items, sealed set untouched). Correct out of 45 per
  variant, ALLaM with its correct format on the raw question / Qwen 1.5B majority after cleanup and rewrite:
  English 42 / 36, MSA 44 / 22, Najdi 40 / 16, mixed 45 / 23, **Arabizi 9 / 2**.
  - **Qwen 1.5B is the wrong small model for Arabic.** It answers English well and little else, so only English stays on it.
  - **A standard router costs more than always-large here:** 116% per success on 30 dev-test items, because Qwen's failed
    attempts still burn compute. Halala's rule that a variant must pay for its small-tier checks brought that to 88%, with
    the same 24 of 30 correct.
  - **Design flaw found on the invalid run, still unfixed:** calibration only counts a loss when the large model was right,
    so where both models fail, failing cheaply looks safe. It needs an absolute floor per variant.
  - **Rewrites used to reach only the small model.** Escalated Arabizi now reaches ALLaM rewritten, and the always-large
    baseline keeps the raw question.
  - The numbers in `runs/local_chatml` are the same run with the wrong prompt format.
- **2026-10-30, variant detection rewritten after testing it on the draft question set.** The old rule compared
  Arabic and Latin *letters*, so one English word inside a long Arabic sentence was only about 7% of the letters and
  the sentence was read as pure dialect: 5 of 30 code-switched questions were misread. Counting *words* per script
  fixes it. Arabizi detection also needed more vocabulary, split into strong markers (one is enough: `wesh`,
  `shlon`, `ya3ni`) and weak function words that also occur in English (`el`, `fi`, `min`), where two are needed.
  Mismatches on the draft set fell from 19 of 150 to 13, and all 13 remaining are draft Najdi questions that are
  really dialect-neutral phrasing. Those are for a native speaker to rewrite; the cue lists were deliberately
  **not** tuned to make them pass, since that would be fitting the detector to our own data.
- **2026-10-30, OpenAI-compatible backend** tested against Ollama's `/v1` endpoint with 4 parallel workers:
  answers, token usage and caching all work. Plugging in Humain's API should only need `base_url`, model names
  and the key (`configs/api.toml`).

## Hypotheses (report them whichever way they come out)

| # | Hypothesis | How you test it | Chart |
|---|---|---|---|
| H1 | A standard cascade saves compute, but its accuracy loss lands mostly on Arabizi and dialect | One global threshold; per-variant loss on test | Per-variant bars |
| H2 | Per-variant calibrated thresholds remove that concentration for a small compute cost | Per-variant vs global thresholds | Per-variant bars, Pareto |
| H3 | Cheap rescue (cleanup, Arabizi to Arabic script) lets the small model keep more dialect traffic and wins back savings | Ablation: rescue on vs off | Ablation table |
| H4 | Unseen variants are safe: a variant with too little calibration data gets escalated, not guessed | Calibrate without Arabizi, test on Arabizi | Robustness table |
| H5 | The Arabizi rewrite is the weak link, and 10 to 20 hand-written examples in its prompt fix most of it | Rewrite meaning kept: no examples vs your examples vs rules; then H3 again | Rewrite accuracy table |
| H6 | The audit generalises: Halala exposes a dialect gap in a router it didn't build | Run `evaluate` on another router's keep/escalate decisions | Before/after per-variant bars |
| H7 | Verification where it pays: stopping at 2 samples when they agree, on variants that prove safe, cuts cost without losing accuracy | Replay using only the first 2 of the 5 saved samples, per variant | Cost per success table |
| H8 | Context that earns its tokens: a shorter system prompt and only the nearest few rewrite examples keep accuracy at lower cost | Short vs current system prompt; all examples vs nearest 3 | Tokens and accuracy table |

## Tonight (about 2 hours)

- [ ] **Check the rules on pre-written code.** If code must be written during the event, treat this repo as a
      reference and rebuild it at kickoff (it is small), or declare it on your project page.
- [ ] `python -m halala smoke`, then `python -m unittest`. Both run on mock models in seconds.
- [ ] Install Ollama and pull a small and a large stand-in: `ollama pull qwen2.5:1.5b`, `ollama pull qwen2.5:7b`.
- [ ] Download `ALLaM-AI/ALLaM-7B-Instruct-preview` from Hugging Face (about 14 GB at full precision).
- [ ] `python -m halala ask --config configs/ollama.toml "وش عاصمة السعودية؟"` to confirm a live call works.
- [ ] Write 15 Arabizi questions with your own Arabic-script rewrites in `data/arabizi_examples.jsonl`
      (format: `data/arabizi_examples.template.jsonl`). Keep them separate from the question set.
- [ ] **Check `data/saudi_parallel.review.html` by hand** (56 groups, 280 items). The 13 flagged rows are draft
      Najdi that reads as formal Arabic; rewrite them, and fix any Arabizi that is not how you would type it.
      Then: `python -m halala seal --data data/saudi_parallel.jsonl --test-fraction 0.20`.
- [ ] Optional: ArabicMMLU's test CSV, converted with `python -m halala convert-mcq --csv <file> --out <file>`.
- [ ] Write the first paragraph of the project page: the problem in two sentences.
- [ ] Sleep.

## Setup, decided 2026-10-30

**No API.** The organizers confirmed there are no ALLaM keys for participants: public models and tools only.
Everything therefore runs locally through Ollama, and `configs/local.toml` is the run config.

| Tier | Model | Speed |
|---|---|---|
| small | `qwen2.5:1.5b` | about 1.5s per call |
| large | `allam-7b-q4` (ALLaM 7B Instruct, community Q4_K_M) | about 4.3s per call |

**Rejected alternative, with the measurement:** ALLaM Q4 as the small tier and ALLaM Q8 as the large tier, so both
tiers would be Humain's model. Measured on 5 probe questions: 4.3s vs 6.6s, only 1.5x apart, with the same answer
on 4 of 5 (both failed the Arabizi one, differently). Too close to route between, so it was dropped. Worth one line
on the project page: it is a documented negative result.

**Budget at this pairing:** about 6 calls per item, roughly 10s per item. 150 items is about 25 minutes, 450 items
about 75 minutes. Writing and hand-checking the questions now costs more than running them, so the question set is
the critical path, not compute.

## Kickoff: what we now know

- **Data is open:** use any data, so your own parallel question set is the main dataset. Seal the test part before
  running anything on it. That sealed set is your evidence for the "unseen or held-out" criterion.
- **Tools and models are open, but no API is provided.** See the setup section above.
- **"Compute" has no stated formula,** but the brief names cost per successful task and latency. Report those, with
  tokens and estimated FLOPs behind them.
- **The submission page has five sections:** about, issue and solution, how it works, presentation, questions.
  Draft in `PROJECT_PAGE.md`.

**How big the question set must be.** The guarantee's strength is set by how many items land in the calibration
split: 45 per variant for epsilon 0.05, 28 for 0.08, 22 for 0.10, 15 for 0.15.

`data/saudi_parallel.jsonl` holds **56 groups, 280 items**. Sealing 20% and splitting the rest 30/50/20 gives
11 sealed groups (55 items), then 14 train / 25 calib / 6 dev-test groups. 25 per variant clears epsilon 0.10.
Writing more groups is the single best way to strengthen the result: 70 groups would reach epsilon 0.08.

**Known limit to state plainly on the project page:** the sealed test set is 55 items and the dev test set 30, so
differences of a few points are inside the noise. Report the per-variant pattern and the cost-per-success gap,
which are large, rather than small accuracy differences.

## Day 1

| Hours | Work | Done when |
|---|---|---|
| H2 to H5 | Data loader, splits by question group, parallel variant set | `python -m halala collect --split train` runs on real data |
| H5 to H8 | Baselines: always-small, always-large, on every split | First README table committed |
| H8 to H9 | Token-tax baseline per variant and model (`tokens`) | One slide of numbers |
| H9 to H14 | Learned router, global calibration, Pareto sweep | H1 answered with a chart |
| H14 to H16 | Start the full collection in the background | Calls landing in `cache/calls.sqlite` |
| H16 to H22 | **Sleep.** The collection runs while you sleep. | |

## Day 2

| Hours | Work | Done when |
|---|---|---|
| H22 to H26 | Per-variant calibration; rescue step with the small model | H2 and H3 answered |
| H26 to H29 | Rewrite with your hand-written examples in the prompt; measure meaning kept | H5 answered |
| H29 to H31 | Audit another router (H6); ablation table (`compare`), regression gate (`check`) | Every component shows what it contributes |
| H31 to H33 | Robustness: held-out variant (H4) | Robustness table |
| H33 to H35 | Finish and document the parallel dataset (license, how it was made, what you checked by hand) | Ready to release |
| H35 to H39 | Demo: English vs Najdi Arabizi side by side, live tokens, compute and tier | Runs offline on your laptop |
| H39 to H44 | Project page and README: finding, method, results, decisions, limits | A judge can follow it without you |
| H44 to H46 | Freeze: fresh clone, `python -m halala run --config ...`, numbers match; record a backup demo video | |
| H46 to H48 | Buffer | |

## If you fall behind, cut in this order

1. Demo polish (the browser page `ask` writes is enough)
2. Cache tier
3. Auditing another team's router (H6): audit the standard one-threshold router instead
4. Robustness H4

Never cut: baselines, per-variant results, the hand-checked dataset, the ablation table, a reproducible run.

## Metrics (fixed now so the goalposts don't move later)

- **Cost per successful task (headline):** total spend over tasks that were right and in time, overall and per variant.
- **Accuracy:** overall and per variant.
- **Floors:** every variant at or above `min_variant_success`; tasks past `latency_limit_s` don't count as successes.
- **Worst-variant gap:** the largest drop, over variants, of policy accuracy below always-large accuracy.
- **Cost vs always-large:** mean primary cost per query, as a percentage.
- **Escalation rate:** overall and per variant.
- **Guarantee check:** on test, did each variant's loss stay at or under ε?

## Project page

The page has five sections: about, issue and solution, how it works, presentation, questions. The working draft is
`PROJECT_PAGE.md`. Replace its placeholders with numbers from the sealed run only.

## Decisions log

Keep this updated during the event; it feeds the Technical Judgment criterion.

| Decision | Alternative | Why | Where |
|---|---|---|---|
| Collect every call once, replay policies offline | Run each policy live | Ablations and sweeps cost nothing and rerun identically | `collect.py`, `cache/calls.sqlite` |
| Split by question group | Split by item | Variants of one question in different splits would leak answers | `data.py` |
| Simple language split as the main design | Keep sampling, the router and certified thresholds | Same accuracy and cost on dev, half the latency, no trained parts, and no reliance on the unverified shared-prompt assumption. The complex version stays as a measured baseline | `policies.simulate`, mode `split` |
| Gemma 3 4B as the small model | Qwen 1.5B | 6 more correct answers on all dev questions (203 vs 197) for 4 points of cost | `configs/local_gemma.toml` |
| The always-large baseline gets the raw question, but Halala's escalations get the rewrite | Raw question on both | The baseline must be the unmodified system, and raw Arabizi is what the large model struggles with | `collect.py`, `large_rescued` |
| Rule-based Arabizi rewrite by default | ALLaM with examples, or ArabiziKit | Lowest cost per correct answer and no model call; ALLaM with examples is more accurate but several times the cost | `[cascade] arabizi` |
| Set ALLaM's prompt format explicitly | Trust Ollama's default | Ollama silently used a generic template; every earlier ALLaM number was wrong and is kept only as a comparison | `configs/allam.Modelfile` |
| Binomial test over a fixed sequence of thresholds | Hand-picked threshold | A stated guarantee instead of a tuned number | `calibrate.py` |
| Variants with too little calibration data escalate | Fall back to the global threshold | Uncertainty should cost compute, never a dialect's accuracy | `[calibrate] small_group_policy` |
| HistGradientBoosting router by default | XGBoost | No extra dependency; XGBoost is one config line away | `[router] model` |
| Answer cache matches only questions with the same numbers | Text similarity alone | "12 plus 34" and "12 plus 43" look almost identical; without the guard the cache cost 8 accuracy points on the smoke run | `policies.nearest_prior` |
| Voting groups answers that say the same thing | Exact-match voting | ALLaM answered الرياض five ways; exact matching scored agreement 0.4 and escalated for nothing, now 1.0 and kept. Known limit: a negation like "ليست الرياض" still joins its core | `scoring.cluster_answers` |
| Sealed test set with a hash and an opening log | Trust yourself not to peek | Evidence for the held-out criterion: the hash proves the file didn't change, the log shows when it was opened | `halala seal`, `--unseal` |
| Check model rewrites before using them | Use whatever comes back | ALLaM's rewrites included a refusal and a leaked chat token; both now fall back to the original | `collect.check_rewrite` |
| Rewrite examples may not match any question in the data | Trust the example file | An example that is also a test question hands the model the answer | `pipeline._guard_leaks` |
| Never keep an empty answer or a refusal | Trust the router | Both can score high on agreement; ALLaM's majority answer was once a refusal | `policies.evaluate`, `scoring.is_refusal` |
| Read data files as utf-8-sig | Plain utf-8 | Windows editors and PowerShell write a byte-order mark, which plain utf-8 rejects | `data.load_jsonl` |
| Detect code-switching by counting words per script | Compare Arabic and Latin letter counts | One English word in a long Arabic sentence is ~7% of its letters but is still a mix; the letter rule misread 5 of 30 | `features._script_word_counts` |
| A variant stays on the small tier only if its savings pay for it (keep rate x large cost > small cost); others go straight to the large model | Run the small tier on everything | The cost-per-success chart showed two variants costing 1.2x to 1.3x always-large, paying for samples that could never be kept | `policies.drop_unprofitable` |
| Headline metric is cost per successful task | Cost per call | The brief asks for it, and it shows what cost per call hides: failed runs still burn compute | `policies.cost_per_success` |
| A right answer past the latency limit isn't a success | Report latency separately | The brief: cheap only counts if the answer is right, and in time | `[floors] latency_limit_s` |
| Extra samples share the first sample's prompt pass | Pay full price per sample | 5 samples of a 7B model at full price cost more than one 34B call, which would wipe out the savings. Verify the serving setup supports it (API `n>1` or a prompt cache) | `[cascade] shared_prefill` |
