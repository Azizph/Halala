Model `qwen2.5:1.5b`, 30 items. The small tier sees the cleaned and rewritten prompt; the large tier sees the raw question.

| Variant | n | Small, greedy | Small, majority of samples | Large, raw question | Mean agreement | Agreement when majority right | Agreement when wrong |
|---|---|---|---|---|---|---|---|
| en | 6 | 100% | 100% | 100% | 0.97 | 0.97 | n/a |
| msa | 6 | 17% | 17% | 100% | 0.33 | 0.60 | 0.28 |
| najdi | 6 | 17% | 17% | 83% | 0.37 | 0.60 | 0.32 |
| arabizi | 6 | 0% | 0% | 17% | 0.63 | n/a | 0.63 |
| mixed | 6 | 33% | 33% | 83% | 0.43 | 0.80 | 0.25 |

Tokens per correct answer (multiple of English in brackets). Failed runs count as spend.

| Variant | Plain: one call, raw question | Cleanup and rewrite, one call | Cleanup and rewrite, majority of samples |
|---|---|---|---|
| en | 78 (1.0x) | 40 (1.0x) | 52 (1.0x) |
| msa | 77 (1.0x) | 270 (6.8x) | 425 (8.2x) |
| najdi | 92 (1.2x) | 268 (6.7x) | 389 (7.5x) |
| arabizi | 566 (7.3x) | no correct answers | no correct answers |
| mixed | 94 (1.2x) | 128 (3.2x) | 188 (3.6x) |