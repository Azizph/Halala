### Run `local`: test split, 30 items

Small model `qwen2.5:1.5b`, large model `allam-7b-q4-inst`. Cost is estimated FLOPs, shown relative to always using the large model.

Floors: every variant at 80% success or better, and a task only succeeds if answered within any seconds.

| Policy | Accuracy | Worst variant vs always-large | Cost per success vs always-large | Cost vs always-large | Sent to large model | p95 latency | Meets floors |
|---|---|---|---|---|---|---|---|
| Always small | 36.7% | -83.3 pts (MSA) | 42% | 19% | 0% | 8.8s | no |
| Always large | 80.0% | 0.0 pts (English) | 100% | 100% | 100% | 4.0s | no |
| Agreement, one threshold | 90.0% | 0.0 pts (English) | 89% | 100% | 77% | 38.7s | no |
| Router, one threshold | 90.0% | 0.0 pts (English) | 89% | 100% | 77% | 38.7s | no |
| Halala: router, per-variant thresholds | 90.0% | 0.0 pts (English) | 75% | 84% | 83% | 32.3s | no |
| Halala + answer cache | 90.0% | 0.0 pts (English) | 75% | 84% | 83% | 32.3s | no |

#### Accuracy by variant

| Variant | Always small | Always large | Router, one threshold | Halala: router, per-variant thresholds | Halala: sent to large |
|---|---|---|---|---|---|
| English | 100.0% | 100.0% | 100.0% | 100.0% | 17% |
| MSA | 16.7% | 100.0% | 100.0% | 100.0% | 100% |
| Najdi | 16.7% | 83.3% | 83.3% | 83.3% | 100% |
| Arabizi | 16.7% | 16.7% | 66.7% | 66.7% | 100% |
| Mixed | 33.3% | 100.0% | 100.0% | 100.0% | 100% |

#### Cost per successful task, by variant

1.0x is always-large on English. Failed tasks still count as spend, so a variant that fails often costs more per success.

| Variant | Always small | Always large | Router, one threshold | Halala: router, per-variant thresholds |
|---|---|---|---|---|
| English | 0.2x | 1.0x | 0.2x | 0.4x |
| MSA | 1.2x | 1.0x | 1.3x | 1.0x |
| Najdi | 1.2x | 1.1x | 1.5x | 1.1x |
| Arabizi | 1.2x | 6.9x | 1.8x | 1.4x |
| Mixed | 0.6x | 1.0x | 1.1x | 1.0x |

#### Guarantee check (epsilon = 0.1, delta = 0.1)

Loss is the share of questions Halala got wrong that the large model got right. Thresholds are set per detected variant; this table groups by the dataset's variant labels.

| Variant | Loss on test | Within epsilon |
|---|---|---|
| English | 0.0% | yes |
| MSA | 0.0% | yes |
| Najdi | 0.0% | yes |
| Arabizi | 0.0% | yes |
| Mixed | 0.0% | yes |

![Cost per success by variant](cost_per_success.png)

![Compute vs accuracy](pareto.png)

![Accuracy by variant](variants.png)
