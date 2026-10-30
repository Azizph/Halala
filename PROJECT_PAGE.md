# Halala: project page draft

`[RESULT]` marks a number still to come. Fill each one from the final runs, and delete anything that doesn't hold up.

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

The Dialect Tax before and after Halala, on all 225 development questions. Each cell shows correct answers out of 45, then real
seconds per correct answer as a multiple of English:

| Way of writing | ALLaM alone | With Halala |
|---|---|---|
| English | 42, 1.0x | 42, 1.0x |
| Formal Arabic | 44, 0.9x | 44, 0.9x |
| Najdi | 40, 1.0x | 40, 1.0x |
| Arabizi | 8, **8.2x** | 32, **1.1x** |
| Mixed Arabic-English | 45, 0.9x | 44, 0.9x |
| **All 225** | **179 correct, 0.54 seconds each** | **202 correct, 0.42 seconds each** |

Those development numbers overstate the Arabizi fix. On 15 fresh questions, written by a separate agent that never saw the word
list, ALLaM got 1 right as typed and 2 after the rewrite, against 14 of 15 in proper Arabic.

On unseen questions, sealed before development began: `[RESULT]`.

---

## How it works

A question comes in and is cleaned up, then Halala detects its form. Arabizi is rewritten into Arabic script by rules and a word
list, with no model call. Arabic goes to ALLaM. English can go to a smaller model when the hardware has room for both. A free
check catches empty or refused answers, and every answer's real cost is recorded.

**How it was tested**

- **Unseen questions:** the same 56 questions in five forms, with 11 of them sealed before development. A hash proves they didn't
  change, and every opening is logged.
- **Outside benchmark:** 100 hard questions from MBZUAI's Dialectal Arabic MMLU, in 7 forms, on both models. Nobody on this project
  wrote them.
- **Real measurements:** seconds come from the server's own clock, and failed attempts count as spend.
- **Tests and checks:** unit tests on mock models, and a regression check on the tax table.

**What didn't work**

| Idea | What happened |
|---|---|
| A word list to turn Saudi dialect into formal Arabic | Took Saudi from 45 to 48 of 100, short of the net gain of 5 set beforehand, so it was dropped |
| A learned router with certified thresholds and repeated sampling | No better than the simple design, and slower |
| Asking a model to rewrite Arabizi | Every version lost to the rules |
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

**Is the Dialect Tax fixed?** No. The Arabizi gap is much smaller, keeping Arabic on ALLaM avoids the cheap-model cost, and Saudi is
still open.

**How do you know the numbers aren't overfitted?** The test questions were sealed before development, and their hash shows they
didn't change. The questions were written by the same person as the rules, so fresh Arabizi was tested too, and that test showed
the rewrite doesn't yet carry over to unseen text.

**What was the biggest mistake?** Ollama silently ran ALLaM with the wrong prompt format, which invalidated the early numbers. Later,
real measurement overturned a token estimate that made one design look cheapest.

**What doesn't this show?** These results use a community build of ALLaM 7B, not Humain's served models. The test sets are small, so
a difference of a few points can be noise. Arabizi may do worse on topics the word list has never seen.
