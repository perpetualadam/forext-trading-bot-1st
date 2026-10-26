# R.71 Operational Integration Gap Register

Code in `forex_bot/` is not automatically on the path. Research under `data/research/` is not the bot.

| Gap | Exists as | Missing connection |
| --- | --- | --- |
| Broker trailing stop | Absent | No stop-amend call from profit protection |
| Breakeven | Absent | No caller and no function |
| Partial close | Entry partial-fill status in unreachable code | No remaining-units state machine |
| Close confirmation | `PositionClose` parser returns P and L | Caller deletes the local row without a unit match |
| Close identity | Client id on the open order only | Close request has none |
| Broker stop evidence | Price fields and a hit function that returns false | No read of a live stop transaction |
| Strategy and AI entry | Implemented after line 1191 | Blocked at line 1139 |
| Sizing and currency | Functions are callable | Entry does not call them, and the quote branch is not GBP |
| Restart | RAM dicts | No position reload |
| PostgreSQL | Helpers | Not integration-tested |
| Linux runtime | Same source | WSL cannot import `oandapyV20` |
| Research containment | R.56–R.65 | Not imported by `run_bot` |
| Profitability | Reports say it was not assessed | No new evidence |

R.68 and R.70 are not gaps. They are present in the operational modules cited in the matrix.
