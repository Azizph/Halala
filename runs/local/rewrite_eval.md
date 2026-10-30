45 dev Arabizi questions. The large model answers in every arm. Cost per correct answer is relative to the upper bound.

| Arm | Correct | Rewrites rejected | Similarity to Najdi | Cost per correct answer |
|---|---|---|---|---|
| Raw Arabizi (no rewrite) | 9 of 45 | 0 | 0.01 | 5.6x |
| Rules, no word list | 24 of 45 | 0 | 0.61 | 1.8x |
| Rules + word list | 31 of 45 | 0 | 0.86 | 1.3x |
| Rules + word list, plus the raw text | 33 of 45 | 0 | 0.38 | 1.6x |
| ArabiziKit (no model call) | 15 of 45 | 0 | 0.38 | 2.9x |
| ArabiziKit + large model spelling fix | 10 of 45 | 3 | 0.35 | 11.8x |
| Small model rewrite | 4 of 45 | 0 | 0.15 | 14.3x |
| Small model rewrite + examples | 6 of 45 | 0 | 0.24 | 22.5x |
| Large model rewrite | 15 of 45 | 2 | 0.44 | 7.4x |
| Large model rewrite + examples | 26 of 45 | 0 | 0.59 | 17.5x |
| Large model rewrite + 4 nearest examples | 22 of 45 | 0 | 0.54 | 9.1x |
| Hand-checked Najdi (upper bound) | 40 of 45 | 0 | 1.00 | 1.0x |