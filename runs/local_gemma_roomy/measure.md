60 dev questions one model at a time, with no cache. Active seconds are the server's own evaluation time. Load seconds are the time spent loading models. Wall seconds are what a user waits.

| Arm | Correct | Active seconds per correct | vs first row | Active | Load | Wall | Tokens out | Prompt tokens evaluated |
|---|---|---|---|---|---|---|---|---|
| Always large, raw question, current instruction | 47 of 60 | 0.61 | 100% | 29 | 9 | 39 | 396 | 731 |
| Halala, current instruction | 54 of 60 | 0.52 | 85% | 28 | 38 | 67 | 263 | 992 |