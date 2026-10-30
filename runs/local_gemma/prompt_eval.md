225 dev questions. Cost per correct answer is an estimate from tokens, relative to always using the large model with the current instruction, so compare each Halala arm with the always-large arm on the same instruction. It counts prompt tokens the server reuses, and treats an output token like an input token. Times are left out because older cached calls carry a 2-second connection delay: `measure` reports real compute.

| Arm | Correct | Tokens in | Tokens out | Tokens per question | Cost per correct |
|---|---|---|---|---|---|
| Always large, raw question, current instruction | 179 of 225 | 44.4 | 5.5 | 49.9 | 100% |
| Always large, raw question, no instruction | 194 of 225 | 15.3 | 20.0 | 35.3 | 65% |
| Always large, raw question, no instruction, first sentence only | 188 of 225 | 15.3 | 14.6 | 29.9 | 57% |
| Halala, current instruction | 204 of 225 | 42.2 | 4.5 | 46.6 | 75% |
| Halala, "Answer briefly." | 212 of 225 | 29.2 | 11.5 | 40.7 | 64% |
| Halala, "أجب باختصار." | 211 of 225 | 29.0 | 11.5 | 40.4 | 63% |
| Halala, no instruction | 213 of 225 | 15.7 | 24.4 | 40.1 | 57% |
| Halala, no instruction, first sentence only | 209 of 225 | 15.7 | 14.6 | 30.3 | 46% |

Correct by form:

| Arm | en | msa | najdi | arabizi | mixed |
|---|---|---|---|---|---|
| Always large, raw question, current instruction | 42 | 44 | 40 | 8 | 45 |
| Always large, raw question, no instruction | 43 | 45 | 45 | 17 | 44 |
| Always large, raw question, no instruction, first sentence only | 41 | 45 | 45 | 15 | 42 |
| Halala, current instruction | 43 | 44 | 40 | 32 | 45 |
| Halala, "Answer briefly." | 43 | 45 | 44 | 35 | 45 |
| Halala, "أجب باختصار." | 43 | 45 | 44 | 34 | 45 |
| Halala, no instruction | 44 | 45 | 45 | 35 | 44 |
| Halala, no instruction, first sentence only | 42 | 45 | 45 | 35 | 42 |