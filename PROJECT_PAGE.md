# Halala: project page draft

---

## About

**Halala**, the smallest unit of the Saudi riyal, measures what a correct AI answer costs for each way of writing Arabic, and
brings that cost down. Challenge 2: Deliver AI with Less Compute.

Built by Abdulaziz Althabit. This is a student entry, tested on a community build of ALLaM 7B, not Humain's served models, and
it isn't endorsed by Humain.

---

## Issue and solution

### The issue

Every AI answer costs compute, right or wrong, so the real price is the cost of a correct answer. That price depends on how you
write. Ask ALLaM in English and a correct answer costs 1. Type the same question in Arabizi, Arabic in Latin letters and numbers
like `wesh 3asmat el sa3odiya?`, and it costs about 8 times as much. Hard questions in Saudi dialect cost about 1.2 times.

That's the **Dialect Tax**, and average scores hide it. The usual way to save compute, sending work to a cheaper model, adds to
it: Gemma 3 4B pays 1.5 to 1.9 times its English cost on Arabic, while ALLaM pays 1.0 to 1.2 times.

### The solution

Halala is a thin layer in front of the model. It does three things:

1. **Measures the tax** for each way of writing, so a gap can't hide in an average.
2. **Removes what it can before the model runs,** at no compute cost.
3. **Spends compute only where it buys right answers,** and keeps Arabic on the model built for it.

### Results

The Dialect Tax before and after Halala, on 55 sealed questions that nobody saw until one logged run. Each cell shows correct
answers out of 11, then real seconds per correct answer as a multiple of English:

| Way of writing | ALLaM alone | With Halala |
|---|---|---|
| English | 11, 1.0x | 11, 1.0x |
| Formal Arabic | 10, 1.1x | 11, 1.0x |
| Najdi | 10, 1.1x | 10, 1.1x |
| Arabizi | 2, **8.1x** | 8, **1.5x** |
| Mixed Arabic-English | 11, 1.0x | 11, 1.1x |
| **All 55** | **44 correct, 0.37 seconds each** | **51 correct, 0.30 seconds each** |

That's 18.5% less real compute per correct answer. With 11 questions in each form, one question moves a form by 9%, so the form
figures are rough.

On 30 more Arabizi questions, written blind by a separate agent that never saw the code, ALLaM got 1 right as typed and Halala got
24, against 28 in proper Arabic. Without its list of real Arabic words, Halala got 14. That batch looks easier than the one before
it, because the previous version of the rewrite got 23 there and 18 on the earlier one.

On the 225 development questions, right answers rise from 179 to 208, and Arabizi from 8 to 38 of 45. The rewrite was built on those
questions, so they overstate it.

---

## How it works

A question comes in and is cleaned up, then Halala detects its form. Arabizi is rewritten into Arabic script by rules and a list
of real Arabic words, with no model call. Arabic goes to ALLaM. English can go to a smaller model when the hardware has room for
both. A free check catches empty or refused answers, and every answer's real cost is recorded.

**How it was tested**

- **Unseen questions:** the same 56 hand-checked questions in five forms, with 11 of them sealed before development. A hash proves
  they didn't change, and every opening is logged. They were opened once.
- **Blind Arabizi:** 60 questions in two batches, written by a separate agent that never saw the code. Each batch ran once on a
  frozen rewrite, under a keep-or-drop rule set beforehand.
- **Outside benchmark:** 100 hard questions from MBZUAI's Dialectal Arabic MMLU, in 7 forms, on both models. Nobody on this project
  wrote them.
- **Real measurements:** seconds come from the server's own clock, and failed attempts count as spend. The machine's speed drifts
  between runs, and the sealed run replays identical prompts from a cache, which keeps that drift out of most of its comparison.
- **Tests and checks:** unit tests on mock models, a regression check on the tax table, and a fresh clone that reproduced every
  correct-answer count.

**What didn't work**

| Idea | What happened |
|---|---|
| A word list to turn Saudi dialect into formal Arabic | Took Saudi from 45 to 48 of 100, short of the net gain of 5 set beforehand, so it was dropped |
| A learned router with certified thresholds and repeated sampling | No better than the simple design, and slower |
| Asking a model to rewrite Arabizi | Every version lost to the rules |
| The first Arabizi rewrite | 2 of 15 on its first unseen test, against 14 in proper Arabic, so it was rebuilt around real Arabic words |
| English to the small model on one 4 GB GPU | 169% of ALLaM alone in mixed traffic, against 85% with room for both, so it's a setting |

---

## Presentation

1. A real receipt for a wrong answer.
2. A realistic user asking the way they actually type.
3. One question followed through the trace.
4. The traffic stream, with the tax shrinking live.
5. The before-and-after Dialect Tax table, including what didn't work.

---

## Questions

**Isn't this just a router?** Barely. The contribution is measuring the tax by form, and a free fix for the biggest gap. A learned
router was tested and didn't earn its place.

**Is the Dialect Tax fixed?** No. Arabizi still costs 1.5 times English on the sealed test, keeping Arabic on ALLaM avoids the
cheap-model cost, and Saudi is still open.

**How do you know the numbers aren't overfitted?** The test questions were sealed before development, and their hash shows they
didn't change. The questions were written by the same person as the rules, so blind Arabizi was tested too. The first test showed
the rewrite didn't carry over to unseen text, so it was rebuilt, and each new version had to beat the last one on questions it
hadn't seen.

**What was the biggest mistake?** Ollama silently ran ALLaM with the wrong prompt format, which invalidated the early numbers. Later,
real measurement overturned a token estimate that made one design look cheapest.

**What doesn't this show?** These results use a community build of ALLaM 7B, not Humain's served models. The test sets are small, so
a difference of a few points can be noise. Arabizi may do worse on words the lists don't hold.
