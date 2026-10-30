# Halala timeline

Updated 22:25 Fri 2026-10-30. All times are Saudi time (AST).

**Deadline: 20:00 Sat 2026-10-31, about 21.5 hours away. ASSUMED until the builder confirms it.** The builder said only "8pm", and the repo states no deadline.
**Status: ON TRACK, if that date holds.** Submission is planned for 16:00, after a full night's sleep. If the overnight work fails, it moves to about 17:30. 18:00 is the latest, which keeps a 2-hour buffer.

## Next 3 actions

1. **Builder, now:** confirm the date and time zone of "8pm", and approve the commit (T19).
2. **Builder, by 23:00:** write the 15 fresh Arabizi questions (T16), then check the demo's Arabic (T17).
3. **Lead, by 22:45:** decide on `num_ctx` (flag 1), restart prompt-eval (T4), and code `measure` (T5) while it runs.

## Schedule

T1 is done. Estimates are in minutes. GPU jobs run one at a time. Overnight rows run without the builder, and count as done only after the 08:00 check.

| Task | Owner | Estimate | Depends on | Target | Status |
|---|---|---|---|---|---|
| T2 Record real timings | Lead | 10 | None | 22:30 | Looks done in `models.py`; lead to confirm |
| T19 Confirm deadline, approve commit | Builder | 2 | None | 22:35 | Waiting |
| T3 Fix form detector | Lead | 45 | None | 22:45 | Fix looks written at 22:16; lead to confirm |
| T16 15 fresh Arabizi questions | Builder | 15 | None | 22:50 | Not started |
| T17 Check the demo's Arabic | Builder | 10 | None | 23:00 | Not started |
| T4 Finish prompt-eval | Lead | 30 GPU (listed 10) | T3, flag 1 | 22:45-23:15 | Stopped in part 2 of 8; not running |
| T5 Build `measure`, measure compute | Lead | 45 + 30 GPU | T2 | Code 22:45-23:30, GPU 23:30-00:00 | Context probe ended by 22:26; `measure` not written |
| T6 Choose the instruction | Lead | 10 | T4, T5 | 00:00-00:10 | Blocked |
| Held slot: re-collect (flag 2) | Lead | Up to 45 GPU | T6 | 00:10-00:55 | Not on the list |
| Builder sleeps | Builder | 450 | T16, T17, T19 | By 00:30, up at 08:00 | Nothing needs the builder after 23:00 |
| T7 Optional: "restate formally" test | Lead | 30 + 15 GPU | T6 | 00:55-01:40 | First cut |
| T8 Robustness suite | Lead | 45, part GPU | T3-T6, T16 | 01:40-02:25 | Not started |
| T18 Optional: friend translates | Builder | Depends on friend | None | Use only if in by 08:30 | Not asked yet |
| T9 Check the demo live | Lead, builder | 30 GPU | T3-T6, T17 | 08:30-09:00 | Not started; flag 4 |
| T10 Commit all work; design freeze | Lead, builder approves | 10 | T6, T8, T9, T19 | 09:00 | Needs approval |
| T11 Fresh-clone check | Lead | 30 | T10 | 09:10-09:40 | Not started |
| T12 Run the sealed test once | Lead | 30 GPU (listed 15) | T10, T11 | 09:45-10:15 | One try only |
| T13 Rewrite `PROJECT_PAGE.md` | Lead | 45 + 20 (flag 5) | T12 | 10:15-11:20 | Draft has out-of-date claims |
| T14 Build 8 to 10 slides | Lead | 60 | T12, T13 | 11:20-12:20 | Not started |
| Break | Everyone | 40 | None | 12:20-13:00 | Planned |
| T15 Record and edit the video | Builder | 90, part GPU (listed 60) | T9, T12, T14, T17 | 13:00-14:30 | Script ready |
| Final check, commit, submit (flag 5) | Lead, builder | 90 | T13-T15 | 14:30-16:00 | Not on the list |
| Buffer | Nobody | 240 | None | 16:00-20:00 | Keep empty |

## Waiting on the builder

- **Tonight:** date and time zone, commit approval (T19), T16 and T17. T8 can't finish without T16. Ask the friend for T18 if it's still wanted, but don't wait for the reply.
- **Saturday:** approve the second commit and any push, be free 13:00-14:30 for T15, and be there to submit by 16:00.
- **Yes or no:** was the dataset hand-check done, and were the rules on pre-written code checked? The page claims the first. Both boxes in `PLAN.md` are unticked, which may only mean the list wasn't updated.

## Cut list, in order

1. **T7**, if T6 isn't done by 01:00.
2. **T18**, if it isn't in by 08:30.
3. **Part of T8:** reuse the existing dialect audit. Keep fresh Arabizi, because the page promises that result.
4. **T15 editing and T14 length:** one clean take, 8 slides.
5. **Part of T9 and T11:** check only the video's questions, and reuse the current Python setup in the clean copy.

**Never drop:** T10, the sealed test (T12), the slides (T14), the video (T15), the corrected claims in T13, the 2-hour buffer and the night's sleep.
**Hard stop:** T12 starts by 12:15, whatever is unfinished. Any later, T13 to T15 and submission don't fit before 18:00.

## Top 3 schedule risks

1. **The GPU queue is longer than the list shows,** by at least 80 minutes, and more if flag 1 goes the wrong way. The video needs the GPU too, so nothing else can run during recording.
2. **The sealed test has one try.** A crash means a second logged opening, and a design change afterwards spoils the result. So T11 runs right before it, on mains power, with the builder awake and no changes after the 09:00 freeze.
3. **Tonight's work is only on this laptop.** 24 changed and 30 new files, including the whole demo, are uncommitted. Ask the builder to approve a safety commit and push tonight, between GPU jobs. Keep the laptop plugged in: it sleeps after 15 minutes on battery.

## Flags for the lead (task list unchanged)

1. **`num_ctx`:** once set in a config, it changes every cache key. Every call would miss the cache, and T4 grows from about 30 to about 75 GPU minutes. Decide before restarting T4.
2. **Re-collect:** the instruction is in the cache key too, and `collect` runs Gemma 3 times on all 225 questions. A new instruction means redoing the collect and the router, then `demo/build_examples.py`. With the same instruction, the results still predate T3, so a mostly cached re-run is needed.
3. **Longer slots:** T4 has about 650 uncached calls. T12 alternates the two models on each question, and T5 will show what that costs. T15 allows for live retakes.
4. **T9:** I can't find the 8 checks. `demo/README.md` has 3 native-speaker checks and `VIDEO_SCRIPT.md` has 5 pre-recording steps. Where is the list?
5. **Not on the list:** the second commit after T12, the push, the submission, and old numbers outside `PROJECT_PAGE.md`. Those are in `README.md` (no results yet), `PLAN.md` ("half the latency"), `demo/numbers.js` and `VIDEO_SCRIPT.md`, and must be fixed before T15.
