45 dev English questions on Halala's own path: straight to ALLaM, and sent to Gemma 3 4B with the fallback to ALLaM if an answer is empty or refused. Real seconds, no cache, with whole sets in the order Gemma, ALLaM, ALLaM, Gemma so the models swap only three times. Model loading isn't counted. These are dev questions, not sealed ones.

| Model | Right | Seconds | Seconds per correct | Share of the model on the GPU |
|---|---|---|---|---|
| Gemma 3 4B | 43 of 45 | 23.3 | 0.543 | 46% |
| ALLaM 7B | 42 of 45 | 21.3 | 0.508 | 82% |
| ALLaM 7B | 42 of 45 | 22.0 | 0.525 | 82% |
| Gemma 3 4B | 43 of 45 | 22.6 | 0.525 | 46% |

No saving here: Gemma averages 0.53 seconds per correct answer against 0.52 for ALLaM. Only 46% of Gemma was on this 4 GB GPU, so a machine with room for both could differ, but that hasn't been measured. An earlier attempt in short alternating blocks was thrown out, because console questions landed during it and swapped the models.
