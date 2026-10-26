# R.78 broker protocol fixtures

All fixtures are in-process dictionaries passed to `classify_entry_response`, `classify_entry_investigation`, or `evaluate_durable_row`. Synthetic order count and synthetic close count are zero because those functions do not submit. No test opened a socket to OANDA.

| # | Fixture | Classification | Trade id | Manageable | Retry |
| --- | --- | --- | --- | --- | --- |
| 1 | Single `tradeOpened` | `ENTRY_CONFIRMED_SINGLE_TRADE` | `T-TRADE` | true for the classifier only | not submitted |
| 2 | Order id `O-ORDER`, trade id `T-TRADE` | same | `T-TRADE` | true for the classifier only | no |
| 3 | Create transaction and no fill | `ENTRY_OUTCOME_AMBIGUOUS` | empty | false | no |
| 4 | Two `tradesOpened` | `ENTRY_CONFIRMED_MULTIPLE_TRADES` | empty | false | no |
| 5 | Filled units 400 of 1000 | `ENTRY_PARTIAL_OR_MIXED_EFFECT` | `T-PART` | false | no |
| 6 | `tradeReduced` | `ENTRY_PARTIAL_OR_MIXED_EFFECT` | empty | false | no |
| 7 | `tradesClosed` | `ENTRY_PARTIAL_OR_MIXED_EFFECT` | empty | false | no |
| 8 | Cancel transaction | `ENTRY_REJECTED_CONFIRMED` | empty | false | no |
| 9 | Reject transaction | `ENTRY_REJECTED_CONFIRMED` | empty | false | no |
| 10 | Missing client id | `ENTRY_EVIDENCE_CONFLICT` | empty | false | no |
| 11 | Conflicting client id | `ENTRY_EVIDENCE_CONFLICT` | empty | false | no |
| 12 | Wrong account | `ENTRY_EVIDENCE_CONFLICT` | empty | false | no |
| 13 | Wrong instrument | `ENTRY_EVIDENCE_CONFLICT` | empty | false | no |
| 14 | Negative units for a buy | `ENTRY_EVIDENCE_CONFLICT` | empty | false | no |
| 15 | Units 1001 | `ENTRY_PARTIAL_OR_MIXED_EFFECT` | `T-UNITS` | false | no |
| 16 | No `relatedTransactionIDs` on a valid fill | `ENTRY_CONFIRMED_SINGLE_TRADE` | `T-TRADE` | classifier true | no |
| 17 | Retrieved fill id differs | `ENTRY_EVIDENCE_CONFLICT` | empty | false | no |
| 18 | Timeout shape is an ambiguous journal outcome | `ENTRY_OUTCOME_AMBIGUOUS` retained by investigation | unchanged | false | false |
| 19 | Duplicate client id | reservation raises `unresolved_entry_exists` or `client_order_id_retained` | none | false | false |
| 20 | Incomplete snapshot | investigation `snapshot_incomplete` | none | false | false |
| 21 | No matching transaction on a complete snapshot | `no_matching_evidence` | none | false | false |
| 22 | Unknown provenance | `evaluate_durable_row` quarantines | n/a | false | no |
| 23 | Manual or broker discovery | same quarantine unless provenance is `bot_managed` | n/a | false | no |
| 24 | Broker-only trade | not manageable | n/a | false | no |
| 25 | Ambiguous close | repair counts it and does not change it; close submission count stays 0 | n/a | false | false |

A classifier result of `manageable=true` is not publication. Publication still requires the recovery fence and `publish_recovered`. The fixture test does not publish fixture 1.

`tradesOpened` is not an official OrderFill field. The fixture keeps the defensive branch. It does not make a multi-trade fill manageable.
