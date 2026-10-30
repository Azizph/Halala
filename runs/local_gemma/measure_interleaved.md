60 dev questions in mixed order, so models swap, with no cache. Active seconds are the server's own evaluation time. Load seconds are the time spent loading models. Wall seconds are what a user waits.

| Arm | Correct | Active seconds per correct | vs first row | Active | Load | Wall | Tokens out | Prompt tokens evaluated |
|---|---|---|---|---|---|---|---|---|
| Always large, raw question, current instruction | 47 of 60 | 0.91 | 100% | 43 | 1 | 45 | 369 | 741 |
| Halala, current instruction | 53 of 60 | 1.54 | 169% | 82 | 1 | 91 | 262 | 969 |