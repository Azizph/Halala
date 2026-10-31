Source: MBZUAI/Dialectal-Arabic-MMLU (CC BY 4.0), 100 questions asked in every form, with the same instruction for every model. Chance is 25%. Run after the sealed test, and Halala's rewrite plays no part.

qwen3:4b's row is not a fair result: it spent its 64-token limit reasoning and rarely reached an answer, which is why it scores below chance. Nothing in the submission quotes it.

Right answers out of 100:

| Model | English | Formal Arabic | Saudi | Emirati | Syrian | Egyptian | Moroccan |
|---|---|---|---|---|---|---|---|
| allam-7b-q4-inst | 58 | 58 | 46 | 51 | 53 | 53 | 54 |
| gemma3:4b | 53 | 44 | 39 | 41 | 38 | 40 | 36 |
| qwen3:4b | 14 | 14 | 9 | 10 | 8 | 10 | 11 |
| qwen2.5:7b | 69 | 49 | 48 | 57 | 41 | 46 | 50 |
| qwen2.5:1.5b | 48 | 43 | 41 | 40 | 37 | 33 | 31 |

The Dialect Tax: tokens per right answer, as a multiple of the same model on English:

| Model | English | Formal Arabic | Saudi | Emirati | Syrian | Egyptian | Moroccan |
|---|---|---|---|---|---|---|---|
| allam-7b-q4-inst | 1.0x | 1.0x | 1.2x | 1.1x | 1.1x | 1.1x | 1.1x |
| gemma3:4b | 1.0x | 1.5x | 1.6x | 1.5x | 1.6x | 1.6x | 1.9x |
| qwen3:4b | 1.0x | 1.2x | 1.8x | 1.6x | 2.0x | 1.7x | 1.6x |
| qwen2.5:7b | 1.0x | 1.8x | 1.9x | 1.6x | 2.2x | 2.0x | 1.9x |
| qwen2.5:1.5b | 1.0x | 1.4x | 1.5x | 1.5x | 1.6x | 1.9x | 2.1x |