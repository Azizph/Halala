# Halala: project page draft

Draft for the hackathon page. Early numbers are labelled as early. Replace every `[RESULT]` with a number from the
sealed run, and delete anything that doesn't hold up.

---

## About

**Halala** (the smallest unit of the Saudi riyal) lowers the cost of a correct AI answer without leaving any dialect
behind.

Most cost-saving work asks how cheap one call can get. Halala asks what each *correct answer* costs, and who pays more
for it. Challenge 2: Deliver AI with Less Compute.

Built by Abdulaziz Althabit.

---

## Issue and solution

### The issue

Failed runs still burn compute, so a cheap model that gets something wrong isn't cheap. The usual way to save compute is to
send easy work to a small model. But "easy" is usually judged on formal text, and people in Saudi Arabia don't only type
formal Arabic. They write Najdi, they mix Arabic and English, and they write Arabizi (Arabic in Latin letters and numbers,
like `wesh 3asmat el sa3odiya?`).

ALLaM 7B on 45 development questions in each form:

| Question written in | Correct | Tokens per correct answer |
|---|---|---|
| English | 42 of 45 | 53 |
| Formal Arabic | 44 of 45 | 49 |
| Najdi | 40 of 45 | 52 |
| Mixed Arabic-English | 45 of 45 | 47 |
| Arabizi, as typed | 9 of 45 | 293 |
| Arabizi, rule-based rewrite first | 31 of 45 | 68 |

ALLaM handles dialect and mixed Arabic-English very well, and it has one measurable gap. A correct answer to an Arabizi
question costs about 5.5 times as much as one in English, because the failed attempts are still paid for. These numbers use
a community build of ALLaM 7B on a laptop. The sealed test results are below.

### The solution

Halala does three things:

1. **Audits cost per successful task for each dialect**, so a gap can't hide inside an overall average.
2. **Rescues Arabizi cheaply**, with a rule-based rewrite and a Najdi word list. It needs no model call, and it took ALLaM's
   Arabizi score from 9 to 31 of 45 on development questions.
3. **Escalates where it must**, using a separate threshold for each dialect, so no dialect pays for the savings. A dialect
   stays on the small model only if that saves compute overall and the kept answers clear an accuracy floor.

### Results

Measured on a sealed test set of `[RESULT]` questions that were never used during development.

| | Always large model | Standard router | Halala |
|---|---|---|---|
| Cost per successful task | 100% | `[RESULT]` | `[RESULT]` |
| Accuracy | `[RESULT]` | `[RESULT]` | `[RESULT]` |
| Worst dialect's accuracy | `[RESULT]` | `[RESULT]` | `[RESULT]` |
| Every dialect clears the floor | `[RESULT]` | `[RESULT]` | `[RESULT]` |

---

## How it works

1. **Clean up.** Remove diacritics and stretching characters, and convert Arabic-Indic digits. This costs almost nothing.
2. **Rewrite Arabizi.** Rules and a 125-word Najdi list convert it to Arabic script, with no model call. They beat every
   alternative tested: ALLaM's own rewrite got 15 of 45, ALLaM with 16 examples 26, and ArabiziKit 15, against 31 for the
   rules, at a fraction of the cost per correct answer. The word list was written after seeing development questions, so
   the rules alone (24 of 45) are the safer guide to unseen text.
3. **Ask the small model several times.** Agreement between answers is a cheap check. Answers that say the same thing in
   different words count as agreeing.
4. **Route.** A small classifier predicts whether the small model's answer can be trusted, using cheap signals only:
   script, dialect cues, Arabizi patterns and agreement.
5. **Keep or escalate.** Each dialect has its own threshold, chosen with a statistical test so its accuracy loss stays under a
   set limit. A dialect with too little calibration data always escalates, so uncertainty costs compute instead of accuracy.
   A dialect also has to earn the small model: if it wouldn't save compute, or the kept answers miss the floor, it goes
   straight to the large model. Empty answers and refusals are never kept. Escalated questions reach the large model
   rewritten, while the always-large baseline gets the raw question.

**How this maps to the brief**

| Challenge point | In Halala |
|---|---|
| Model choice per task | The router, with per-dialect thresholds |
| Context that earns its tokens | The rewrite and its examples run only on Arabizi `[RESULT: H8]` |
| Verification where it pays | More checking on dialects that fail, less on those that prove safe `[RESULT: H7]` |
| Cost per successful task | The headline metric, overall and per dialect |
| Accuracy and latency floors | A task only succeeds if it's right and in time; every dialect must clear the floor |

**How it was tested**

- **The dataset:** the same questions in English, formal Arabic, Najdi, Arabizi and mixed, checked by a native speaker.
- **Sealed test set:** split off before development. Its hash is recorded and every opening is logged.
- **No leakage:** all forms of a question stay in the same split, and rewrite examples can't overlap the test questions.
- **Component checks:** each part is removed in turn to show what it adds `[RESULT: ablation table]`.
- **Reproducible:** every model call is cached, so one command reproduces every number without calling a model again.

---

## Presentation

1. **The hook:** the same question in English and in Arabizi, with the cost of each correct answer shown live.
2. **The issue:** failed runs burn compute, and the bill isn't shared equally.
3. **The audit:** cost per successful task by dialect.
4. **The standard router:** it saves compute, and shows where the loss lands `[RESULT]`.
5. **Halala:** rescue, verify, escalate.
6. **Results:** the sealed test table, and cost against accuracy.
7. **Why you can trust it:** sealed test set, removing each part, reproducible numbers.
8. **Decisions and limits:** what was tried, what was dropped, what this doesn't show.

---

## Questions

Likely questions, with honest answers to prepare.

**Isn't this just a router?** The router is one part. The contribution is measuring cost per successful task per dialect, and
certifying each dialect separately. Most routers report one average, which can hide a dialect that's failing.

**How do you know the numbers aren't overfitted?** The test set was sealed before development. Its hash proves it didn't
change, and the log shows when it was opened.

**Doesn't asking the model five times cost more?** Yes, which is why the extra answers reuse the first one's pass over the
prompt, and answers are short. `[RESULT: H7]` shows how far the sampling can be cut.

**Why not always use the large model?** It's the accuracy baseline, but `[RESULT]` shows how much of its cost is
unnecessary. On Arabizi it gets 9 of 45 as typed, so paying for it alone doesn't help: a rewrite with no model call
takes that to 31.

**What was the biggest mistake?** Ollama silently ran ALLaM with the wrong prompt format, which understated its accuracy
badly: mixed Arabic-English went from 35 to 45 of 45 once fixed. Every number here comes from the corrected setup, and the
template is pinned in the repo.

**Does this work on other models?** The audit and the thresholds work with any pair of models. The numbers have to be measured
again for each one.

**What doesn't this show?** These results use a community build of ALLaM 7B on a laptop, not Humain's served models. Dialect
detection is simple cue-word matching. Arabizi still misses the 80% floor. The word list may not carry over to new topics. The sealed test set is small, so
differences of a few points are noise. Savings on Arabic-script questions are limited because the small model is weak there.
