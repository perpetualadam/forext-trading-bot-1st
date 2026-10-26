# R.71 Historical Feature Preservation

The question is whether each recovered requirement is in the operational path. "In the file" and "on the path" are separate columns.

| Requirement | In the working tree | On the current path | Preserved |
| --- | --- | --- | --- |
| Activate near 67 percent of original target | Yes, default 0.67 | Yes, for a permitted in-memory position | Yes, as a local rule |
| ATR(14) times 0.5 giveback | Yes. Smoothing is a simple average, not Wilder | Yes, same branch | Yes, with that smoothing method |
| 4-pip fallback | Yes | Yes, only when ATR is missing | Yes |
| Ratchet that does not loosen | Yes | Yes, in memory | Yes until restart |
| Broker trailing stop | No | No | Not preserved, because it was not found |
| Breakeven | No | No | Not found |
| Partial close | No strategy close | No | Not found |
| 20-pip stop and 2R target | Yes | No. The call is behind the entry block | Code preserved, not reachable |
| Optional ATR stops | Yes, default off | No | Code preserved, not reachable |
| Six-pair universe | Yes | The list can be iterated. Orders are blocked | Parsing preserved |
| Risk percent sizing | Yes | Call site blocked. Direct function works | Formula preserved, not reachable |
| GBP account correctness | Currency field exists. Stop risk for EUR_USD stays in USD | Not on the entry path | Not preserved as a correct GBP sizer |
| Observation-only discoveries | Yes | Yes | Preserved from R.68 |
| Fail-closed incomplete snapshots | Yes | Yes | Preserved from R.70 |
| Production entries blocked | Yes | Yes | Preserved |

Restart loses MFE, so the ratchet is not preserved across a process boundary.
