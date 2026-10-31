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

Arabic isn't one way of writing. It's many dialects, down to niche ones like Khuzestani in Iran, with no agreed spelling, and Cypriot
Arabic in Cyprus, written in a Latin-based alphabet. AI doesn't treat them all the same.

Ask ALLaM, Humain's Arabic model, the same question in English, formal Arabic and five dialects, and you can watch it happen. On a
public benchmark question about Mars, it's right in English and formal Arabic and wrong in most of the dialects. That's one question,
picked to show the gap, but the totals across all 100 lean the same way: ALLaM gets 58 right in both English and formal Arabic, and 46
to 54 in Saudi, Emirati, Syrian, Egyptian and Moroccan, though with 100 questions a few points can be noise.

A shop that charged more for your accent would be a scandal. With AI, it's just the bill. Every answer costs tokens, the pieces of
text an AI reads and writes, right or wrong, so the real price is the cost of a right answer. When that price rises because of how
you write, that's the **Dialect Tax**: the extra you pay, and the wrong answers you get, for writing the way you speak. Average
scores hide it. ALLaM pays the smallest tax of the four models that ran properly, at 1.1 to 1.2 times its English cost by tokens, and
the other three pay 1.5 to 2.2 times (`runs/local_gemma/scorecard.md`).

Niche dialects like Khuzestani and Cypriot Arabic aren't on the benchmark, so what they pay hasn't been measured here. A gap nobody
measures is a gap nobody fixes.

### The solution

Halala measures the Dialect Tax: what each way of writing really pays for a right answer. Then it tests fixes, one leak at a time. A
leak is any way of writing that pays the tax. Halala sits in front of the model as a thin layer:

1. **Measure.** Price a right answer for each way of writing, so a gap can't hide in an average.
2. **Fix the worst leak,** before the model runs, with no extra AI.
3. **Test it on held-back questions,** and keep it only if it wins.

**Arabizi is one use case.** It's Arabic typed in Latin letters and numbers, like `el osboo3 kam yom?`, how many days are in a week.
ALLaM answers 30. Arabizi pays the steepest tax measured, and it was small enough to test properly in a hackathon. It isn't on the
benchmark, so it was tested on separate, simpler questions. Halala rewrites it into Arabic letters using rules and about 250,000 real
Arabic words, so ALLaM goes from 3 to 32 of 41 held-back questions right. On 11 of those, a right answer falls from 317 tokens to 65,
against 50 in English. That gap is smaller, not closed. The saving so far is almost all on Arabizi and follows how much Arabizi is in
the traffic. It's one tested example of what a fix can do, not the compute story: wasted compute sits unevenly, and Halala shows where.

Halala hasn't fixed a dialect yet, and its own test is what says so. A word list for Saudi made a net gain of 3 of 100, short of the 5
set beforehand, so the list was dropped. Arabizi is a way of writing, so a dictionary can reach most of it: the same 30 questions get
1 right as typed and 28 in Arabic letters. What causes a dialect's gap hasn't been measured, and it may not be spelling, so each
dialect needs its own fix and its own test.

Saudi stays next, because it scores lowest on ALLaM on the benchmark. Emirati, Syrian, Egyptian and Moroccan stay open, and the niche
dialects start with measuring what they pay. The goal is the same for all of them: a right answer back down to the halala, however
you write.

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
  wrote them. A live replay of ALLaM's 700 calls matched on every token count and moved 5 right-or-wrong marks
  (`runs/local_gemma/live_replay.md`).
- **Real measurements:** token counts and seconds both come from the server, and failed attempts count as spend. Speed drifts between
  runs, and the sealed run replays identical prompts from a cache, which keeps that drift out of most of its comparison.
- **Tests and checks:** 77 tests on mock models and saved calls, a regression check on the tax table, and a fresh clone that reproduced the development
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

1. One public benchmark question run live in seven forms, and what all 100 say.
2. The Dialect Tax across the dialects and four models.
3. One use case, Arabizi: a wrong answer anyone can spot, the same question in Arabic, then one question through the trace to its receipt.
4. The traffic stream, then the held-back results.
5. Where each leak stands: what didn't work, and the next leak.

---

## Questions

**Isn't this just a router?** Barely. The contribution is measuring the tax by form, and a free fix for the biggest gap. A learned
router was tested and didn't earn its place.

**Why does Arabizi matter at all?** On its own it's a habit from the old internet. It matters as the clearest case of a wider tax: on
a public benchmark, every dialect costs ALLaM more per right answer than formal Arabic and gets fewer right. It's also the worst leak, and
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
