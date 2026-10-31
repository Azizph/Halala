# Halala: project page draft

---

## About

**Halala** is the smallest unit of the Saudi riyal, a coin that has almost left daily life because inflation made it too small to
bother with. This project borrows the name for one goal: bringing the cost of a right AI answer back down to the halala, however you
write. Challenge 2: Deliver AI with Less Compute.

Built by Abdulaziz Althabit. This is a student entry, tested on a community build of ALLaM 7B, not Humain's served models, and
it isn't endorsed by Humain.

---

## Issue and solution

### The issue

A shop that charged more for your accent would be a scandal. That's close to what happens when people ask an AI in Arabizi: they pay
for every answer, and most come back wrong.

Every AI answer costs tokens, the pieces of text it reads and writes, right or wrong, so the real price is the cost of a right answer.
On sealed questions, a right answer in English takes ALLaM about 50 tokens, and formal Arabic and Najdi take about the same. Type the
question in Arabizi, Arabic in Latin letters and numbers like `wesh 3asmat el sa3odiya?`, and it takes 317, because most answers come
back wrong.

That's the **Dialect Tax**: the extra you pay, and the wrong answers you get, for writing the way you speak. Average scores hide it.
The usual way to save compute, sending work to a cheaper model, adds to it. On a public benchmark of 100 hard questions, ALLaM pays
1.1 to 1.2 times its English cost on five dialects, by tokens, the least of the four models that ran properly. The other three pay
1.5 to 2.2 times (`runs/local_gemma/scorecard.md`).

Arabizi itself is a habit from the old internet, when most tech had no Arabic, so it's fair to ask why it matters. A 2018 Saudi study
found young users keeping it as a code among friends ([Alghamdi and Petraki](https://doi.org/10.3390/socsci7090155)), and it's the
clearest case of something much wider. On those 100 hard questions, ALLaM gets 58 right in English and 46 to 54 in five dialects, with
Saudi lowest, where a right answer costs about 1.2 times as much, by tokens.

### The solution

Halala is a thin layer in front of the model that works through the tax, leak by leak:

1. **Measures the tax** for each way of writing, so a gap can't hide in an average.
2. **Fixes the worst leak first,** before the model runs, with no model call.
3. **Moves to the next,** with Arabic staying on ALLaM, the model built for it.

This entry goes after one leak, Arabizi, because it's the worst and it's small enough to work on and test properly in a hackathon.
Saudi and the other dialects come next. The goal is back down to the halala: what English pays, however you write.

### Results

The Dialect Tax before and after Halala, on 55 sealed questions, held back until one logged test. Each cell shows correct answers
out of 11, then tokens for one right answer:

| Way of writing | ALLaM alone | With Halala |
|---|---|---|
| English | 11, 50 | 11, 50 |
| Formal Arabic | 10, 52 | 11, 48 |
| Najdi | 10, 51 | 10, 51 |
| Arabizi | 2, **317** | 8, **65** |
| Mixed Arabic-English | 11, 47 | 11, 47 |
| **All 55** | **44 correct, 62 tokens each** | **51 correct, 51 tokens each** |

Arabizi with Halala is 64.5 exactly, rounded up here. `sealed.md` prints 64 because Python rounds a half to the even number.

**The saving is almost all on Arabizi:** 6 of the 7 extra right answers and 118 of the 122 tokens saved. The seventh is one Formal
Arabic question, which the rewrite never touches. Across all 55, total tokens fell 4.5% and right answers rose from 44 to 51, which
makes tokens per right answer 17.6% lower. That figure depends on the traffic: a fifth of these questions are Arabizi. By calculation
it falls to about 10% if a tenth are and about 6% if a twentieth are, or 16%, 8% and 4% counting Arabizi's change alone. With 11
questions in each form, one more right answer would take 317 to 211, so the form figures are rough.

Token counts barely move between runs on the same setup, but they aren't compute, because writing a token costs far more than reading
one. Model time tells the same story: Arabizi went from 8.1 to 1.5 times English, and seconds per right answer fell 18.5% on this
mix. That counts the model's seconds, not the rewrite's, which takes about 0.04 seconds a question after a 7-second load.

On the last 30 blind Arabizi questions, written by a separate AI agent that never saw the code, ALLaM got 1 right as typed and Halala
got 24, at 60 tokens per right answer, against 28 when the same questions are written in Arabic letters, at 52. Without its 250,000
real words, keeping the rules and a short hand list, Halala got 14. That batch looks easier than the one before it, because the
previous version of the rewrite got 23 there and 18 on the earlier one.

**When typing gets messy:** 75 Arabizi questions outside the sealed set were retyped ten ways, under a rule set before the run: a way
of typing holds up if Halala keeps two-thirds of its right answers and doesn't fall below ALLaM alone. Six held up, including emojis,
stretched letters and swapped letters. Four didn't: from 65 right answers, one typo leaves 39, no vowels 38, no number letters 26 and
two typos 17. Halala never fell below ALLaM alone, and two full runs matched on every row (`runs/local_gemma/messy_typing.md`). All
capitals passes on the total, but gets 14 of the 30 questions unseen at the freeze. It's a one-line fix, left out so the sealed result
stays valid.

On the 225 development questions, right answers rise from 179 to 208, and Arabizi from 8 to 38 of 45, at 327 tokens per right answer
down to 55. The rewrite was built on those questions, so they overstate it.

---

## How it works

A question comes in, Halala detects its form, then cleans it up. Arabizi is rewritten into Arabic script by a short hand list, about
250,000 real Arabic words and rules, with no model call. Arabic goes to ALLaM. English can go to a smaller model, though that setting
is off in every result here, and it saved nothing when tested on a machine without room for both. Every answer's real cost is
recorded.

**How it was tested**

- **Held-back questions:** the same 56 hand-checked questions in five forms, with 11 of them sealed before any model ran on them. A
  hash proves they didn't change, and every test run is logged. They were tested once, and reopened once afterwards to count tokens
  from the saved answers, with no new model calls. The rows also sit in `data/saudi_parallel.jsonl`, the file they were split from, so
  the seal is a discipline rather than a lock.
- **Blind Arabizi:** 60 questions in two batches, written by a separate AI agent that never saw the code. Each batch was first scored
  on a frozen rewrite, and the last 30 came under a keep-or-drop rule set beforehand. The first 30 then helped improve the rewrite, so
  only the last 30 are unseen by the final version. Those were rerun later to count tokens, with the same right answers.
- **Outside benchmark:** 100 hard questions from MBZUAI's Dialectal Arabic MMLU, in 7 forms, on five models. Nobody on this project
  wrote them.
- **Real measurements:** token counts and seconds both come from the server, and failed attempts count as spend. Speed drifts between
  runs, and the sealed run replays identical prompts from a cache, which keeps that drift out of most of its comparison.
- **Tests and checks:** 72 tests on mock models, a regression check on the tax table, and a fresh clone that reproduced the development
  and blind counts.

**What didn't work**

| Idea | What happened |
|---|---|
| A word list to turn Saudi dialect into formal Arabic | A net gain of 3 of 100, short of the 5 set beforehand, so it was dropped |
| A learned router with certified thresholds and repeated sampling | No better than the simple design, and slower |
| Asking a model to rewrite Arabizi | No version beat the rules plus word list |
| The first Arabizi rewrite | 2 of 15 on its first unseen test, against 14 in Arabic letters, so it was rebuilt around real Arabic words |
| English to the small model | No saving: 0.53 seconds per correct answer against 0.52 on ALLaM, on 45 development questions, and 169% of ALLaM alone in mixed traffic on one 4 GB GPU. It stays a setting, off in every result here |

---

## Presentation

1. A wrong answer anyone can spot: ALLaM says a week has 30 days when the question is typed in Arabizi.
2. The same question in Arabic, where ALLaM gets it right.
3. One question followed through the trace, with its receipt.
4. The traffic stream, with the tax shrinking live.
5. The results, what didn't work, and the next leak.

---

## Questions

**Isn't this just a router?** Barely. The contribution is measuring the tax by form, and a free fix for the biggest gap. A learned
router was tested and didn't earn its place.

**Why does Arabizi matter at all?** On its own it's a habit from the old internet. It matters as the clearest case of a wider tax: on
a public benchmark, every dialect costs more per right answer than formal Arabic and gets fewer right. It's also the worst leak, and
one small enough to work on and properly test in a hackathon.

**Doesn't a bigger model already read Arabizi?** Often, yes. This challenge is about less compute, and a small model plus a free
dictionary got 24 of 30 unseen Arabizi questions, with no extra AI running.

**Does it save compute on every question?** No. The saving is almost all on Arabizi. English and Arabic use about the tokens they did:
Arabic stays on ALLaM on purpose, and English on the smaller model saved nothing when tested. The point is that compute is wasted
unevenly, so the biggest leak can be found and shrunk for free. How much that saves overall depends on how much of the traffic is
Arabizi.

**Is the Dialect Tax fixed?** No. Arabizi still takes 65 tokens per right answer on the sealed test, against 50 in English, keeping
Arabic on ALLaM avoids the cheap-model cost, and Saudi is still open.

**How do you know the numbers aren't overfitted?** The test questions were sealed before any model ran on them, and their hash shows
they didn't change. The questions and the rules came from the same side, so blind Arabizi was tested too. The first test showed the
rewrite didn't carry over to unseen text, so it was rebuilt, and each new version had to beat the last one on questions it hadn't
seen.

**What was the biggest mistake?** Ollama silently ran ALLaM with the wrong prompt format, which invalidated the early numbers. Later,
real measurement overturned a token estimate that made one design look cheapest.

**Why report tokens, when a token estimate misled you?** That was an estimate. These are real counts from the server. Tokens are how
AI is priced and they barely move between runs, so they're the clearest unit to show. They still aren't compute, so real seconds sit
beside them, and cost choices were made on seconds.

**What doesn't this show?** These results use a community build of ALLaM 7B, not Humain's served models. The test sets are small, so
a difference of a few points can be noise. Arabizi may do worse on words the lists don't hold, and no test question has come from a
real message yet.
