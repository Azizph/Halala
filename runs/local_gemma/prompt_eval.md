225 dev questions. Cost per correct answer is relative to always using the large model. Time is the sum of measured call times, and some come from earlier cached runs.

| Arm | Correct | Tokens in | Tokens out | Tokens per question | Cost per correct | Seconds per question |
|---|---|---|---|---|---|---|
| Always large, raw question, current instruction | 180 of 225 | 44.4 | 5.6 | 50.0 | 100% | 3.7 |
| Halala, current instruction | 203 of 225 | 42.2 | 4.5 | 46.6 | 76% | 3.6 |
| Halala, "Answer briefly." | 212 of 225 | 29.2 | 11.4 | 40.5 | 64% | 4.1 |
| Halala, "أجب باختصار." | 211 of 225 | 29.0 | 11.4 | 40.3 | 64% | 4.3 |
| Halala, no instruction | 213 of 225 | 15.7 | 24.7 | 40.3 | 58% | 5.4 |

Correct by form:

| Arm | en | msa | najdi | arabizi | mixed |
|---|---|---|---|---|---|
| Always large, raw question, current instruction | 42 | 44 | 40 | 9 | 45 |
| Halala, current instruction | 43 | 44 | 40 | 31 | 45 |
| Halala, "Answer briefly." | 43 | 45 | 44 | 35 | 45 |
| Halala, "أجب باختصار." | 43 | 45 | 44 | 35 | 44 |
| Halala, no instruction | 44 | 45 | 45 | 35 | 44 |