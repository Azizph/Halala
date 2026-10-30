60 dev questions one model at a time, with no cache. Active seconds are the server's own evaluation time. Load seconds are the time spent loading models. Wall seconds are what a user waits.

| Arm | Correct | Active seconds per correct | vs first row | Active | Load | Wall | Tokens out | Prompt tokens evaluated |
|---|---|---|---|---|---|---|---|---|
| Always large, raw question, current instruction | 47 of 60 | 0.68 | 100% | 32 | 8 | 42 | 396 | 731 |
| Always large, raw question, "Answer briefly." | 51 of 60 | 1.19 | 174% | 61 | 1 | 64 | 940 | 688 |
| Always large, raw question, no instruction, first sentence only | 48 of 60 | 1.23 | 179% | 59 | 1 | 62 | 859 | 669 |
| Always large, raw question, no instruction | 50 of 60 | 1.55 | 227% | 78 | 1 | 82 | 1312 | 135 |