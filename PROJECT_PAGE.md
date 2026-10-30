# Halala: project page draft

Draft for the hackathon page. Development numbers are labelled as such. Replace every `[RESULT]` with a number from the
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

Failed runs still burn compute, so a cheap model that gets something wrong isn't cheap. And people in Saudi Arabia don't only
type formal Arabic. They write Najdi, they mix Arabic and English, and they write Arabizi (Arabic in Latin letters and
numbers, like `wesh 3asmat el sa3odiya?`).

ALLaM 7B on 45 development questions in each form:

| Question written in | Correct | Tokens per correct answer |
|---|---|---|
| English | 42 of 45 | 53 |
| Formal Arabic | 44 of 45 | 49 |
| Najdi | 40 of 45 | 52 |
| Mixed Arabic-English | 45 of 45 | 47 |
| Arabizi, as typed | 9 of 45 | 293 |

ALLaM handles dialect and mixed Arabic-English very well, and it has one measurable gap. A correct answer to an Arabizi
question costs about 5.5 times as much as one in English, because the failed attempts are still paid for. These numbers use
a community build of ALLaM 7B on a laptop.

### The solution

Halala is deliberately simple:

1. **Audit cost per correct answer for each form**, so a gap can't hide inside an overall average.
2. **Rewrite Arabizi with no model call**, using rules and a Najdi word list. That took ALLaM from 9 to 31 of 45.
3. **Send each question to the cheapest model that can handle it.** English goes to a small model once. Everything else goes
   to ALLaM. No sampling, no classifier, no trained parts.

We built the complex version first: repeated sampling, a learned router and statistically certified thresholds per dialect.
Then we measured it. It kept only English on the small model anyway, and its savings depended on an unverified assumption.
The simple design matched its accuracy at the same cost with half the latency, so we chose it.

### Results

All 225 development questions, estimated compute, relative to always using ALLaM on the raw question:

| Design | Correct of 225 | Cost per correct answer |
|---|---|---|
| Always ALLaM | 180 | 100% |
| ALLaM + rewrite | 202 | 85% |
| **Halala** | **203** | **76%** |

Measured on a sealed test set of 55 items that weren't used to build or tune anything:

| | Always ALLaM | Standard router | Full pipeline | Halala |
|---|---|---|---|---|
| Correct | `[RESULT]` | `[RESULT]` | `[RESULT]` | `[RESULT]` |
| Cost per correct answer | 100% | `[RESULT]` | `[RESULT]` | `[RESULT]` |
| Worst form's accuracy | `[RESULT]` | `[RESULT]` | `[RESULT]` | `[RESULT]` |

---

## How it works

1. **Clean up.** Remove diacritics and stretching characters, and convert Arabic-Indic digits. This costs almost nothing.
2. **Detect the form** from the script and a few marker words: English, Arabizi, or Arabic.
3. **Rewrite Arabizi.** Rules and a 125-word Najdi list convert it to Arabic script, with no model call. They beat every
   alternative tested: ALLaM's own rewrite got 15 of 45, ALLaM with 16 examples 26, and ArabiziKit 15, against 31 for the
   rules, at a fraction of the cost per correct answer. The word list was written after seeing development questions, so
   the rules alone (24 of 45) are the safer guide to unseen text.
4. **Route.** English goes to Gemma 3 4B once. Everything else goes to ALLaM 7B, rewritten if it was Arabizi.
5. **One cheap check.** If the small model returns nothing or refuses, ALLaM answers instead.

**How this maps to the brief**

| Challenge point | In Halala |
|---|---|
| Model choice per task | English to the small model, Arabic to ALLaM. Gemma answered English as well as ALLaM (43 vs 42 of 45) |
| Context that earns its tokens | The Arabizi rewrite adds no prompt tokens. Sending ALLaM 16 examples cost far more per correct answer |
| Verification where it pays | We measured sampling and dropped it. The one check left is free: an empty answer or a refusal |
| Cost per successful task | The headline metric, overall and per form |
| Accuracy and latency floors | Reported per form. Arabizi still misses the 80% floor at 69% |

**How it was tested**

- **The dataset:** the same 56 questions in English, formal Arabic, Najdi, Arabizi and mixed, checked by a native speaker.
- **Sealed test set:** split off before development. Its hash is recorded and every opening is logged.
- **No leakage:** all forms of a question stay in the same split, and rewrite examples can't overlap the test questions.
- **Component checks:** 12 ways of handling Arabizi compared on the same questions, and the full pipeline kept as a baseline.
- **Reproducible:** every model call is cached, so one command reproduces every number without calling a model again.

---

## Presentation

1. **The hook:** the same question in English and in Arabizi, with the cost of each correct answer shown live.
2. **The issue:** failed runs burn compute, and the bill isn't shared equally.
3. **The audit:** ALLaM is strong on four forms and has one gap.
4. **The fix:** a rewrite with no model call beats every LLM rewrite tested.
5. **The twist:** we built a sophisticated router, measured it, and threw it out.
6. **Results:** the sealed test table.
7. **Why you can trust it:** sealed test set, reproducible numbers, and the mistakes we caught.
8. **Limits:** what this doesn't show.

---

## Questions

Likely questions, with honest answers to prepare.

**Isn't this just a router?** It's barely one, on purpose. The contribution is the audit by form, and a free fix for the gap
it found. We tested a learned router and it didn't earn its place.

**Why not use the router you built?** Across the development data it matched the simple design on accuracy and cost, took
twice the latency, and its savings relied on repeated samples sharing a prompt pass, which we never verified. Without that it
cost 86 to 94% against 72 to 76%.

**How do you know the numbers aren't overfitted?** The test set was sealed before development. Its hash proves it didn't
change, and the log shows when it was opened. The questions were written by the same people as the rules, so we also tested
on fresh Arabizi written afterwards `[RESULT]`.

**Why not always use the large model?** On English the small model is as good, for about half the compute. And on Arabizi,
paying for ALLaM alone doesn't help: it gets 9 of 45 as typed.

**What was the biggest mistake?** Ollama silently ran ALLaM with the wrong prompt format, which understated its accuracy
badly: mixed Arabic-English went from 35 to 45 of 45 once fixed. Every number here comes from the corrected setup, and the
template is pinned in the repo.

**Does this work on other models?** The audit does. The routing has to be measured again for each pair of models.

**What doesn't this show?** These results use a community build of ALLaM 7B on a laptop, not Humain's served models. Compute is
estimated, not measured, and it leaves out the time to load and swap models. Detection is simple marker-word matching.
Arabizi still misses the 80% floor. The word list may not carry over to new topics. The sealed test set is small, so differences
of a few points are noise. Savings come from English only, so they depend on how much traffic is in English.
