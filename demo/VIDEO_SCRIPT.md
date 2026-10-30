# Halala: video script

About 3 minutes, recorded at 1920x1080, in the order the rules ask for. Everything on screen is the working prototype in
live mode, except the coin counts and the results, which are the measured totals from my development run.

## Before recording

1. Start the server with the real models:

   ```bash
   python demo/server.py --config configs/local_gemma.toml
   ```

2. Open `http://127.0.0.1:8770/` in the browser, press F11 for full screen, and keep the zoom at 100%.
3. The header must say `Live: Gemma 3 4B and ALLaM 7B` in green. If it's red (`Mock models`) or copper (`Recorded answers`),
   stop: that take can't be used as the working prototype.
4. Click through every step once, so both models are loaded, then reload the page.
5. Say what's on the screen. Where the script has `[brackets]`, read the real result from that take. If a live answer
   differs from what this script expects, say what it actually did.

Controls: Right and Left arrows move between steps, 1, 2 and 3 switch the example, N opens the numbers, Esc closes them.

## 1. Introduction (0:00 to 0:36)

| Time | On screen | Do | Say |
|---|---|---|---|
| 0:00 | Step 1, Capital city. Both answers are in. | Hold still. Wait for both answers before starting. | "I'm Abdulaziz Althabit, and this is Halala, named after the smallest coin of the riyal. Here's the same question, typed two ways. In English, ALLaM gets it right. In Arabizi, Arabic typed in Latin letters the way a lot of people text, it falls apart." |
| 0:18 | Step 2. Two trays of coins and the 5.5×. | Press Right. | "That costs more than one wrong answer. Each coin is a question, and wrong answers still get paid for. So a right answer in Arabizi costs about five and a half times as much, only because of how it was typed." |

## 2. Solution walkthrough (0:36 to 1:12)

| Time | On screen | Do | Say |
|---|---|---|---|
| 0:36 | Step 3. The rewrite appears, ALLaM answers, the coins flip. | Press Right. Let it play. | "My fix runs before the model. Rules and a word list rewrite Arabizi into Arabic script, with no model call and no tokens. ALLaM goes from 9 to 31 right out of 45, and each right answer falls from 293 tokens to 68. It isn't solved, and the screen says so." |
| 1:00 | Step 3, finished. | Hold still. | "The rest is deliberately simple. English goes to a smaller model, once. Everything else goes to ALLaM. I built a far more complex version first, measured it, and threw it out." |

## 3. A realistic use case, step by step (1:12 to 1:56)

| Time | On screen | Do | Say |
|---|---|---|---|
| 1:12 | Step 4, Live. Empty question box. | Press Right. Click the box and type `wesh akbar sa7ra bil sa3odiya?` | "Imagine someone planning a desert trip, asking a travel assistant the way they text." |
| 1:24 | The steps fill in one at a time. | Press Enter. Move the cursor down each row as it fills. | "Step by step. Halala sees it's Arabizi. It rewrites it in Arabic script, with no model and no tokens. It chooses ALLaM, and shows why. And ALLaM answers: `[the answer on screen]`." |
| 1:44 | The right-hand card fills in. | Move the cursor to the card. | "On the right, the same raw question went straight to ALLaM. That's a real call too, made just now, and it said `[what it said]`. Same model. The only difference is the rewrite." |

## 4. AI in action (1:56 to 2:32)

| Time | On screen | Do | Say |
|---|---|---|---|
| 1:56 | Live, the same question in English. | Click `In English`. Point at the summary line when it appears. | "Now the same question in English. Halala makes a different decision: the smaller model, Gemma. Look at the last line: `[the compute share on screen]` of the compute of going straight to ALLaM." |
| 2:12 | Live, the same question in Najdi. | Click `In Najdi`. | "And in Saudi dialect: no rewrite and no smaller model, because ALLaM handles it well. Halala leaves it alone." |
| 2:24 | The finished steps. | Move the cursor down the rows once. | "That's every question: read it, decide, answer, and count what it cost." |

## 5. Results (2:32 to 3:02)

| Time | On screen | Do | Say |
|---|---|---|---|
| 2:32 | Step 5. The two bars and the headline. | Press Right. | "Across `[225]` development questions, right answers went from `[180]` to `[203]`, and each one takes about `[24]`% less compute. ALLaM was already strong on dialect. It had one gap, and closing it takes no extra model calls." |
| 2:48 | The numbers panel. | Press N. | "Every number, how I tested it, and what this doesn't show are here. This ran on a community build of ALLaM on my laptop, so the real test is Humain's own models. Thanks for watching." |

The figures in step 5 change when the pending runs land, so read them from the screen on the day.
