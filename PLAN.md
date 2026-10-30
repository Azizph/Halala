# Halala: the plan

This is the only plan. If anything else disagrees with it, this file wins. The rules for working on it are in `CLAUDE.md`.

## The problem

Every AI answer costs compute, right or wrong, so the real price is the cost of a correct answer. That price depends on how
you write. Ask ALLaM in English and a correct answer costs 1. Type the same question in Arabizi and it costs about 8 times
as much. Hard questions in Saudi dialect cost about 1.2 times.

That's the **Dialect Tax**, and average scores hide it. The usual way to save compute, sending work to a cheaper model, adds to
it: Gemma pays 1.5 to 1.9 times its English cost on Arabic.

## The solution

Halala is a thin layer in front of the model. It does three things:

1. **Measures the tax** for each way of writing, so a gap can't hide in an average.
2. **Removes what it can before the model runs,** at no compute cost.
3. **Spends compute only where it buys right answers,** and keeps Arabic on the model built for it.

## How it works

A question comes in and is cleaned up, then Halala detects its form. Arabizi is rewritten into Arabic script by rules and a word
list, with no model call. Arabic goes to ALLaM. English can go to a smaller model when the hardware has room for both. A free
check catches empty or refused answers, and every answer's real cost is recorded.

**Where that leaves the tax:** on the development questions, the Arabizi fix takes it from 8 to 32 of 45 correct, and its tax from
8.2 times English to 1.1 times. Across all 225, right answers rise from 179 to 202, at 22% less real compute per correct answer
(`runs/local_gemma/dialect_tax.md`). **On text it hasn't seen, the fix doesn't hold yet:** 15 fresh questions went from 1 to 2 of
15 correct, against 14 of 15 in proper Arabic (`runs/local_gemma/arabizi_fresh.md`). Keeping Arabic on ALLaM avoids the cheap-model
cost. The Saudi gap is still open, and the sealed test is still to run.

## The demo

The old one explained Halala like a slideshow. The new one lets you watch the tax shrink, on real model calls.

- **The Halala console:** an ordinary chat box on the left and a live trace in the middle, showing form detected, rewrite, model
  chosen and answer.
- **A receipt for every answer:** this is the idea to lead with, because it fits the name. Each answer prints a receipt of what
  it cost against the same question unaided, and wrong answers show up as money wasted. Anyone understands a receipt.
- **The big moment:** press one button and a stream of mixed questions runs through ALLaM alone and Halala side by side. Bars for
  each form build up live, and Arabizi's bar visibly drops. It's scale you can see, not one hand-picked example.

Receipts are priced in halalas, where 1 halala is what a correct English answer costs ALLaM, measured in real seconds. Say so on
screen: it's a unit of compute, not a real price.

### The video

1. Open on a real receipt for a wrong answer.
2. Show a realistic user asking the way they actually type.
3. Follow one question through the trace.
4. Run the traffic stream.
5. End on the before-and-after Dialect Tax table, including what didn't work.

If time allows, add one more thing: show that any app can point at Halala with a one-line change, which would make it feel like
a product a Humain engineer could use.

It reuses the live pipeline already in `demo/`, so about 3.5 hours looks realistic, though that pipeline has only been tested on
mock models so far.

## Checklist to 8pm

Deadline: **20:00 Saudi time, Saturday 2026-10-31**. Aim to submit by 17:00 and keep the rest as a buffer. This
doesn't need to be technically exhaustive. Work top to bottom. Tick each item with the time it finished.

**Status: running, resumed by the builder at 00:15.**

| Done | Task | Who | By |
|---|---|---|---|
| [x] | Remove what's off plan, keep one code path, write this file (00:20) | Lead | 00:30 |
| [x] | Commit and push the cleanup (00:15) | Lead | 00:30 |
| [x] | Confirm the deadline (00:20) | Builder | Now |
| [x] | Run `dialect-tax` and choose the instruction by its effect on the tax: the original stays (00:35) | Lead | 01:00 |
| [x] | Save the regression baseline with `check --save` (00:35) | Lead | 01:00 |
| [x] | Build the console: chat box, live trace, receipts (00:30) | Lead | 03:00 |
| [x] | Build the traffic stream and live bars (00:30) | Lead | 04:00 |
| [x] | Run the console on the real models: 225 questions in about 2.5 minutes (00:40) | Lead | 04:30 |
| [x] | Write 15 fresh Arabizi questions, by an agent kept away from the word list (00:40) | Agent | 09:00 |
| [x] | Run the fresh Arabizi questions: 1 to 2 of 15, against 14 in proper Arabic (00:45) | Lead | 09:30 |
| [ ] | Decide whether to build a rewrite that holds on unseen Arabizi | Builder | Now |
| [ ] | Check the 15 fresh questions and the console's Arabic, and say whether the dataset was hand-checked and whether pre-written code is allowed | Builder | 09:00 |
| [ ] | Freeze: commit, check that a fresh clone gives the same numbers | Lead, builder approves | 10:00 |
| [ ] | Run the sealed test once | Lead | 10:30 |
| [ ] | Put the final numbers in `PROJECT_PAGE.md` and the console | Lead | 11:00 |
| [ ] | Build 8 to 10 slides | Lead | 12:30 |
| [ ] | Record the video | Builder | 15:00 |
| [ ] | Final check, commit and push | Lead, builder approves | 16:00 |
| [ ] | Submit | Builder | 17:00 |

**If time runs short, cut in this order:** the one-line API, polish on the live bars, then slides down to 8.

**Never cut:** the sealed test, the slides, the video, or honest numbers. The sealed test must start by 12:15.

## Tried and dropped

Say what didn't work. The evidence is in `runs/`, and the code is in git at `f9ab881`.

| Idea | Result | Evidence |
|---|---|---|
| Saudi word list | 45 to 48 of 100, needed a net gain of 5 | `runs/local_gemma/dialect_rewrite.md` |
| Learned router, thresholds and repeated sampling | No better than the simple design, and slower | `runs/local_gemma/dev/results.md` |
| Model rewrites of Arabizi, with and without examples | All worse than the rules | `runs/rewrite_eval_final.md` |
| English to Gemma on one 4 GB GPU | 169% of ALLaM alone in mixed traffic, 85% with room for both | `runs/local_gemma/measure_interleaved.md`, `runs/local_gemma_roomy/measure.md` |
| Freer replies for dialect and Arabizi | 7 more right answers, but Najdi's tax rose to 2.5 times and Arabizi's to 3.4 | `runs/local_gemma/dialect_tax_instructions.md` |
| Capping answer length | Saved nothing at 24 tokens, and lost accuracy at 16 or fewer | Run on 2026-10-30, 225 dev questions |
| Answer cache for repeated questions | No repeats in the data to reuse | Consultant's review, 2026-10-30 |

## Parked

Ideas that aren't in the plan. They stay here unless the builder moves them onto the checklist.

- Open replies on the benchmark, to see if "reply with only the letter" causes part of the Saudi gap. It needs 100 fresh questions.
- A retry of the Saudi word list on fresh questions, adding `ايش من الجاي` and `الي`.
- Correcting Arabizi misspellings with a word-frequency list.
- A friend from Jazan, Al-Ahsa or the Hijaz translating 15 to 20 questions.
