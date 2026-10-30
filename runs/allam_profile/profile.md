Model `allam-7b`, 40 items. The small tier sees the cleaned and rewritten prompt; the large tier sees the raw question.

| Variant | n | Small, greedy | Small, majority of samples | Large, raw question | Mean agreement | Agreement when majority right | Agreement when wrong |
|---|---|---|---|---|---|---|---|
| en | 8 | 100% | 100% | 100% | 0.93 | 0.93 | n/a |
| msa | 8 | 88% | 88% | 88% | 0.85 | 0.89 | 0.60 |
| najdi | 8 | 88% | 88% | 100% | 0.80 | 0.83 | 0.60 |
| arabizi | 8 | 12% | 12% | 0% | 0.40 | 0.60 | 0.37 |
| mixed | 8 | 88% | 88% | 88% | 0.70 | 0.71 | 0.60 |

Tokens per correct answer (multiple of English in brackets). Failed runs count as spend.

| Variant | Plain: one call, raw question | Cleanup and rewrite, one call | Cleanup and rewrite, majority of samples |
|---|---|---|---|
| en | 80 (1.0x) | 80 (1.0x) | 122 (1.0x) |
| msa | 89 (1.1x) | 89 (1.1x) | 126 (1.0x) |
| najdi | 75 (0.9x) | 86 (1.1x) | 125 (1.0x) |
| arabizi | no correct answers | 1628 (20.3x) | 2039 (16.8x) |
| mixed | 90 (1.1x) | 90 (1.1x) | 134 (1.1x) |