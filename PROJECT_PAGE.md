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

A shop that charged more for your accent would be a scandal, and most of the time you'd get the wrong order as well. That's close to
what happens when people ask an AI the way they really write.

Every AI answer costs tokens, the pieces of text it reads and writes, right or wrong, so the real price is the cost of a right answer.
On questions nobody had seen, a right answer in English takes ALLaM about 50 tokens, and formal Arabic and Najdi take about the same.
Type the question in Arabizi, Arabic in Latin letters and numbers like `wesh 3asmat el sa3odiya?`, and it takes 317.

That's the **Dialect Tax**: the extra you pay, and the wrong answers you get, for writing the way you speak. Average scores hide it.
The usual way to save compute, sending work to a cheaper model, adds to it: Gemma 3 4B pays 1.5 to 1.9 times its English cost on
Arabic, by tokens, while ALLaM pays 1.0 to 1.2 times.

Arabizi itself is a habit from the old internet, when keyboards had no Arabic, so it's fair to ask why it matters. It's the clearest
case of something much wider. On 100 hard questions from a public benchmark, ALLaM gets 58 right in English and 46 in Saudi dialect,
where a right answer costs about 1.2 times as much, by tokens.

### The solution

Halala is a thin layer in front of the model that works through the tax, leak by leak:

1. **Measures the tax** for each way of writing, so a gap can't hide in an average.
2. **Fixes the worst leak first,** before the model runs, with no model call.
3. **Moves to the next,** with Arabic staying on ALLaM, the model built for it.

This entry goes after one leak, Arabizi, because it's the worst and it's small enough to fix and test properly in a hackathon. Saudi
and the other dialects come next. The goal is one halala, however you write.

### Results

The Dialect Tax before and after Halala, on 55 sealed questions that nobody saw until one logged test. Each cell shows correct
answers out of 11, then tokens for one right answer:

| Way of writing | ALLaM alone | With Halala |
|---|---|---|
| English | 11, 50 | 11, 50 |
| Formal Arabic | 10, 52 | 11, 48 |
| Najdi | 10, 51 | 10, 51 |
| Arabizi | 2, **317** | 8, **64** |
| Mixed Arabic-English | 11, 47 | 11, 47 |
| **All 55** | **44 correct, 62 tokens each** | **51 correct, 51 tokens each** |

**The saving is on Arabizi.** The other four forms cost about the same as ALLaM alone. Across all 55, total tokens fell 4.5% and right
answers rose from 44 to 51, which makes tokens per right answer 17.5% lower. That figure depends on the traffic: a fifth of these
questions are Arabizi, and it falls to about 10% if a tenth are, and about 6% if a twentieth are. With 11 questions in each form, one
question moves a form by 9%, so the form figures are rough.

Tokens repeat exactly between runs, but they aren't compute, because writing a token costs far more than reading one. Real seconds
tell the same story: Arabizi went from 8.1 to 1.5 times English, and seconds per right answer fell 18.5% on this test.

On 30 more Arabizi questions, written blind by a separate agent that never saw the code, ALLaM got 1 right as typed and Halala got
24, at 60 tokens per right answer, against 28 in proper Arabic at 52. Without its list of real Arabic words, Halala got 14. That batch
looks easier than the one before it, because the previous version of the rewrite got 23 there and 18 on the earlier one.

On the 225 development questions, right answers rise from 179 to 208, and Arabizi from 8 to 38 of 45, at 327 tokens per right answer
down to 55. The rewrite was built on those questions, so they overstate it.

---

## How it works

A question comes in and is cleaned up, then Halala detects its form. Arabizi is rewritten into Arabic script by rules and a list
of real Arabic words, with no model call. Arabic goes to ALLaM. English can go to a smaller model when the hardware has room for
both, though that setting is off in every result here and saved nothing when tested. A free check catches empty or refused answers,
and every answer's real cost is recorded.

**How it was tested**

- **Unseen questions:** the same 56 hand-checked questions in five forms, with 11 of them sealed before development. A hash proves
  they didn't change, and every opening is logged. They were tested once, and reopened once afterwards to count tokens from the saved
  answers, with no new model calls.
- **Blind Arabizi:** 60 questions in two batches, written by a separate agent that never saw the code. Each batch ran once on a
  frozen rewrite, under a keep-or-drop rule set beforehand.
- **Outside benchmark:** 100 hard questions from MBZUAI's Dialectal Arabic MMLU, in 7 forms, on both models. Nobody on this project
  wrote them.
- **Real measurements:** token counts and seconds both come from the server, and failed attempts count as spend. The machine's speed
  drifts between runs, and the sealed run replays identical prompts from a cache, which keeps that drift out of most of its comparison.
- **Tests and checks:** unit tests on mock models, a regression check on the tax table, and a fresh clone that reproduced every
  correct-answer count.

**What didn't work**

| Idea | What happened |
|---|---|
| A word list to turn Saudi dialect into formal Arabic | Took Saudi from 45 to 48 of 100, short of the net gain of 5 set beforehand, so it was dropped |
| A learned router with certified thresholds and repeated sampling | No better than the simple design, and slower |
| Asking a model to rewrite Arabizi | Every version lost to the rules |
| The first Arabizi rewrite | 2 of 15 on its first unseen test, against 14 in proper Arabic, so it was rebuilt around real Arabic words |
| English to the small model | No saving: 0.53 seconds per correct answer against 0.52 on ALLaM, on 45 development questions, and 169% of ALLaM alone in mixed traffic on one 4 GB GPU. It stays a setting, off in every result here |

---

## Presentation

1. A real receipt for a wrong answer.
2. A realistic user asking the way they actually type.
3. One question followed through the trace.
4. The traffic stream, with the tax shrinking live.
5. The before-and-after Dialect Tax table in tokens, including what didn't work.

---

## Questions

**Isn't this just a router?** Barely. The contribution is measuring the tax by form, and a free fix for the biggest gap. A learned
router was tested and didn't earn its place.

**Why does Arabizi matter at all?** On its own it's a habit from the old internet. It matters as the clearest case of a wider tax: the
less your Arabic looks like a textbook, the more a right answer costs, and the less likely you are to get one. It's also the worst
leak, and one that could be fixed and properly tested in a hackathon.

**Does it save compute on every question?** No. The saving is on Arabizi. English and Arabic cost about what they did: Arabic stays
on ALLaM on purpose, and English on the smaller model saved nothing when tested. The point is that compute is wasted unevenly, so the
biggest leak can be found and closed for free. How much that saves overall depends on how much of the traffic is Arabizi.

**Is the Dialect Tax fixed?** No. Arabizi still takes 64 tokens per right answer on the sealed test, against 50 in English, keeping
Arabic on ALLaM avoids the cheap-model cost, and Saudi is still open.

**How do you know the numbers aren't overfitted?** The test questions were sealed before development, and their hash shows they
didn't change. The questions were written by the same person as the rules, so blind Arabizi was tested too. The first test showed
the rewrite didn't carry over to unseen text, so it was rebuilt, and each new version had to beat the last one on questions it
hadn't seen.

**What was the biggest mistake?** Ollama silently ran ALLaM with the wrong prompt format, which invalidated the early numbers. Later,
real measurement overturned a token estimate that made one design look cheapest.

**Why report tokens, when a token estimate misled you?** That was an estimate. These are real counts from the server. Tokens are how
AI is priced and they repeat exactly between runs, so they're the clearest unit to show. They still aren't compute, so real seconds sit
beside them, and design choices were made on seconds.

**What doesn't this show?** These results use a community build of ALLaM 7B, not Humain's served models. The test sets are small, so
a difference of a few points can be noise. Arabizi may do worse on words the lists don't hold.
