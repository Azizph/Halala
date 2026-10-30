Why raw seconds per correct answer swing between runs, and what the saving is without that swing. English, formal Arabic, Saudi and mixed questions send the same prompts in both arms, apart from digit and spacing cleanup on 27 of the 180, so any difference in their time is the machine changing speed between the arms, not Halala. Taking that difference out gives the last column. The sealed run replays identical prompts from the call cache, which covers 153 of those 180 on the dev questions, so the drift can only reach the rest there.

| Run | Right answers | ALLaM alone, seconds per correct | With Halala, seconds per correct | Raw saving | Second arm slower by | Saving without the drift |
|---|---|---|---|---|---|---|
| `ce3a5ac`, first rewrite | 179 to 202 | 0.541 | 0.425 | 21.4% | 1.02x | 23.2% |
| `0c3e64a`, spelling from real words | 179 to 207 | 0.547 | 0.397 | 27.4% | 1.00x | 27.1% |
| `f9d07d1`, final rewrite | 179 to 208 | 0.481 | 0.407 | 15.4% | 1.17x | 27.9% |
| `f9d07d1`, fresh clone (`dialect_tax_clone.md`) | 179 to 208 | 0.429 | 0.446 | -4.0% | 1.45x | 28.5% |
