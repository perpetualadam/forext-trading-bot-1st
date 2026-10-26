# R.71 Pre-production Implementation Backlog

This order does not authorise the next edit. Production stays NO-GO until a separate review. Profitability is not an item that this backlog can satisfy with a code change.

## Category A — Critical execution safety

| ID | Requirement | Status | Missing | Safety | Depends on | Stage | Tests | Blocks production |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | Broker stop evidence | F16 partial, F37 design | Read a real stop section and do not treat absence as unprotected without a complete section | A false hit or a missed hit mismanages a live row | R.70 snapshot rules | Stage 2 | Synthetic stop sections, both sides | Yes |
| A2 | Close filled units | F20 missing | Match closed units before `close_position` | Local delete can orphan or double-close | A1 | Stage 3 | Timeout, partial units, empty snapshot | Yes |
| A3 | Close identity | F21 missing | One id that survives a timeout | Duplicate `PositionClose` | A2 | Stage 4 | Two overlapping closes | Yes |
| A4 | Partial remainder | F19 missing | Retain unfilled units | A partial fill can look flat | A3 | Stage 4 | Partial fill then a second close | Yes |
| A5 | Concurrency | R.70 generation only | Report dictionary and manage overlap | A stale report can disagree with the book | A2 | Stage 5 | Barrier tests | Yes |
| A6 | Restart | F09 and F38 missing | Reload unresolved closes and observations | Restart forgets protection and exposure | A3, A5 | Stage 6 | Kill and restore with synthetic state | Yes |
| A7 | Currency and sizing | F24 partial | GBP and non-USD quote conversion, margin | Oversize or undersize | Do not enable entries first | Stage 7 | Synthetic GBP, JPY, USD-quote | Yes |

## Category B — Historical trading features

| ID | Requirement | Status | Next action |
| --- | --- | --- | --- |
| B1 | 67 percent activation, ATR giveback, 4-pip fallback, ratchet | Reachable local layer | Preserve. Do not retune while safety stages are open |
| B2 | Broker trailing stop | Missing | Do not add a stop amendment until A1 exists |
| B3 | Breakeven | Missing | Needs an explicit product decision. It is not implied by profit protection |
| B4 | Weekend flatten | Reachable | Keep it on the same close identity as A3 |

## Category C — Strategy and performance

| ID | Requirement | Status |
| --- | --- | --- |
| C1 | Strategy chain | Blocked. Leave blocked |
| C2 | AI and RL entry | Blocked. Research until a separate authorisation |
| C3 | Profitability | Not verified. Needs out-of-sample costs, drawdown, and walk-forward evidence. None was produced |

## Category D — Infrastructure

| ID | Requirement | Status |
| --- | --- | --- |
| D1 | Linux with declared dependencies | Not verified |
| D2 | PostgreSQL | Not integration-tested |
| D3 | Practice-environment plan | Not authorised and not run |

## Category E — Research-only

R.56–R.65 containment, the adaptive-ensemble research stack, and the shadow engine stay out of the order path unless a later architecture decision says otherwise. Passing research tests do not integrate them.

## Recommended next implementation stage

Stage 2 from the R.70 roadmap: broker protection evidence. Do not start it from this audit. Do not enable trading. Do not change the profit-protection formula as part of that stage.
