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

A question comes in and is cleaned up, then Halala detects its form. Arabizi is rewritten into Arabic script by rules and a list
of real Arabic words, with no model call. Arabic goes to ALLaM. English can go to a smaller model when the hardware has room for
both, though that setting is off in every result here and saved nothing when tested. A free check catches empty or refused answers,
and every answer's real cost is recorded.

**Where that leaves the tax:** on the sealed test, 55 questions nobody saw until one logged run, Arabizi goes from 2 to 8 of 11
correct, and its tax from 8.1 times English to 1.5 times (`runs/local_gemma/sealed.md`). Each form has only 11 questions there, so
those figures are rough. **The saving is on Arabizi alone.** English and Arabic cost about what they did, because Arabic stays on
ALLaM on purpose and English on the smaller model saved nothing when tested (`runs/local_gemma/english_small_model.md`). Across all
55, right answers rise from 44 to 51 and total compute falls 5.7%, so compute per correct answer is 18.5% lower on a test that's
one-fifth Arabizi. That figure follows the share of Arabizi in the traffic: about 10% at a tenth, and 5% at a twentieth. On 30 other
Arabizi questions nobody had seen, ALLaM alone gets 1 right and Halala gets 24, against 28 of 30 when the same questions are written in
proper Arabic (`runs/local_gemma/arabizi_fresh3.md`). That batch looks easier than the one before it, because the previous rewrite
got 23 there and 18 on the earlier one. Without its list of real words, this rewrite gets 14 (`runs/local_gemma/arabizi_parts.md`).
On the development questions, which the rewrite was built on, Arabizi goes from 8 to 38 of 45 correct, and right answers across all
225 rise from 179 to 208 (`runs/local_gemma/dialect_tax.md`), with compute per correct answer about 28% lower on the same one-fifth
mix once the machine's speed changes are taken out (`runs/local_gemma/compute_drift.md`). Lead with Arabizi's tax on the sealed test,
and only quote an overall saving with its traffic mix. Keeping Arabic on ALLaM avoids the cheap-model cost. The Arabizi gap is
smaller, not closed, and the Saudi gap is still open.

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
| [x] | Decide whether to build a rewrite that holds on unseen Arabizi: yes, with a hard stop at 08:00 (01:00) | Builder | Now |
| [x] | Repair the Arabizi rules and add word-frequency spelling correction (01:30) | Lead | 08:00 |
| [x] | Write a second fresh batch, by an agent kept away from the code, and run it once when the fix was final. The fix stays: 13 to 18 of 30 blind, 32 to 37 of 45 on development questions, and no form lost (01:35) | Lead, agent | 08:00 |
| [x] | Second rewrite round: fix the general misses, then run it once on a new blind batch. It stays: 23 to 24 of 30 blind, 74% to 80% of the target words, 37 to 38 of 45 on development questions, and no form lost (02:10) | Lead, agent | 08:00 |
| [x] | Check the 60 blind questions, the 15 fresh ones and the console's Arabic, and say whether the dataset was hand-checked and whether pre-written code is allowed: all passed, the dataset was hand-checked, and earlier code is allowed (02:25) | Builder | 09:00 |
| [x] | Freeze: commit, check that a fresh clone gives the same numbers: every form's correct answers match, and so do all 30 unseen rewrites and results, at `f9d07d1` (02:35) | Lead, builder approves | 10:00 |
| [x] | Run the sealed test once: 44 to 51 of 55, Arabizi 2 to 8 of 11, 18.5% less real compute per correct answer on a one-fifth Arabizi mix (02:40) | Lead | 10:30 |
| [x] | Put the final numbers in `PROJECT_PAGE.md` and the console (02:50) | Lead | 11:00 |
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
| English to Gemma | No saving: 0.53 seconds per correct answer against 0.52 on ALLaM, with Gemma only part-way on this GPU, and 169% of ALLaM alone in mixed traffic on one 4 GB GPU | `runs/local_gemma/english_small_model.md`, `runs/local_gemma/measure_interleaved.md` |
| Freer replies for dialect and Arabizi | 7 more right answers, but Najdi's tax rose to 2.5 times and Arabizi's to 3.4 | `runs/local_gemma/dialect_tax_instructions.md` |
| Capping answer length | Saved nothing at 24 tokens, and lost accuracy at 16 or fewer | Run on 2026-10-30, 225 dev questions |
| Answer cache for repeated questions | No repeats in the data to reuse | Consultant's review, 2026-10-30 |
| The first Arabizi rewrite on unseen text | 2 of 15, against 14 in proper Arabic, which is why it was rebuilt | `runs/local_gemma/arabizi_fresh_before.md` |
| Treating a vowel before two consonants as short | About one word in 441, on 90 checked questions | Run on 2026-10-31, 90 questions that were no longer unseen |
| Capping how much a word's commonness counts | Within a word or two either way on 60 checked questions | Run on 2026-10-31, 45 dev and 15 fresh questions |
| Making an untyped hamza free | Cost a blind question: `القمر` became `الأقمار` and `أول` became `أوائل` | `runs/local_gemma/arabizi_fresh2.md` |

## Parked

Ideas that aren't in the plan. They stay here unless the builder moves them onto the checklist.

- Open replies on the benchmark, to see if "reply with only the letter" causes part of the Saudi gap. It needs 100 fresh questions.
- A retry of the Saudi word list on fresh questions, adding `ايش من الجاي` and `الي`.
- Update `main` before submitting: it's GitHub's default branch and it's still at `c1bbe6f`, so a clone misses everything since.
- `test_bad_requests_are_refused` in `demo/test_server.py` fails about one run in ten on Windows. The server refuses a bad address
  without reading the request, so the connection can reset. The console never sends one, so it's left alone after the freeze.
- Rewrite misses left alone: an apostrophe typed for ع (`a'la`), `3ando` becoming `غاندو`, `3alam` read as world when it means flag,
  and words neither list holds, such as `يحطونه`.
- A friend from Jazan, Al-Ahsa or the Hijaz translating 15 to 20 questions.
