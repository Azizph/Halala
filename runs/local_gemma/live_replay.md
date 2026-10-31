The 700 calls behind `scorecard.md` for allam-7b-q4-inst, replayed live on 2026-10-31 through the console's Dialects tab path (`ask_item`), one question after another, and compared with the saved calls in `cache/calls.sqlite`. It took 435 seconds.

Token counts matched on all 700 calls. 7 answers changed, and 5 of those changed from right to wrong or back.

| Form | Saved right | Live right |
|---|---|---|
| English | 58 | 57 |
| Formal Arabic | 58 | 58 |
| Saudi | 46 | 46 |
| Emirati | 51 | 50 |
| Syrian | 53 | 53 |
| Egyptian | 53 | 56 |
| Moroccan | 54 | 54 |

The answers that changed:

| Question | Form | Saved | Live |
|---|---|---|---|
| dmmlu-astronomy-63 | Egyptian | A | C |
| dmmlu-prehistory-37 | Emirati | C | B |
| dmmlu-marketing-16 | Egyptian | A | B |
| dmmlu-abstract_algebra-49 | English | C | B |
| dmmlu-elementary_mathematics-75 | Egyptian | A | C |
| dmmlu-high_school_geography-16 | Moroccan | B | C |
| dmmlu-public_relations-47 | Emirati | D | A |

Right in English and wrong in Saudi: 21 questions saved, 21 live. The other way round: 9 saved, 10 live. The rule for the console's picks, right in English and formal Arabic and wrong in Saudi, finds the same 10 questions both ways.

The temperature is 0, so these moves aren't sampling. The likely cause is the machine's state, such as which call came just before. dmmlu-astronomy-63 in Egyptian came back C in this replay and on one click just after the server started, and A on two later clicks from idle. Clicked twice each from idle, all three picks gave the same marks both times.

The scorecard stays the saved run. This replay doesn't replace its numbers.
