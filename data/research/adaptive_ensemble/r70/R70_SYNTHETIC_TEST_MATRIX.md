# R.70 Synthetic Test Matrix

Harness: R.69 `isolation.py` imported before any `forex_bot` module. Target functions are the real `fetch_broker_positions_detail` and `reconcile_positions_log_only`. The broker object is a `FakeAPI` installed as `oanda_client._api`. Its body is synthetic. The function bodies are not mocked.

All rows below passed on Windows in `test_r70_snapshot.py` unless a row says the behaviour is the known unsafe empty-book path.

| Case | Body or event | Class | Authoritative publish | Previous book | Convergence | Managed book | Observation | `auto_fix` delete | Broker write | Error visible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `{"positions":[]}` | `COMPLETE_EMPTY` | Yes | Replaced with empty | Yes | Unchanged when no permitted live row | No | No in the empty-only test | No | No |
| 2 | `{}` | `INCOMPLETE` | No | Kept | No | Kept | No | No | No | Yes |
| 3 | `{"positions":null}` | `MALFORMED` | No | Kept | No | Kept | No | No | No | Yes |
| 4 | `{"positions":"invalid"}` | `MALFORMED` | No | Kept | No | Kept | No | No | No | Yes |
| 5 | `{"positions":{}}` | `MALFORMED` | No | Kept | No | Kept | No | No | No | Yes |
| 6 | Valid long `EUR_USD` | `COMPLETE_NONEMPTY` | Yes | Replaced | Yes | Not created | Observation-only | No | No | No |
| 7 | Missing instrument beside a valid row | `MALFORMED` | No | None on first read | No | Empty | No | No | No | Yes |
| 8 | Missing short section | `MALFORMED` | No | None | No | Empty | No | No | No | Yes |
| 9 | Units `nope` | `MALFORMED` | No | None | No | Empty | No | No | No | Yes |
| 10 | `NaN` and `Infinity` | `MALFORMED` | No | None | No | Empty | No | No | No | Yes |
| 11 | Long 1000 and short -400 | `CONFLICT` | No | None | No | Empty | No | No | No | Yes |
| 12 | `EUR_USD` and `usd/cad` | `COMPLETE_NONEMPTY` | Yes | Replaced | Yes | Not created | Both observations | No | No | No |
| 13 | Valid row then a row with no sides | `MALFORMED` | No | Previous `EUR_USD` kept | No | Unchanged | Previous not replaced by the bad body | No | No | Yes |
| 14 | Two `EUR_USD` rows | `CONFLICT` | No | None | No | Empty | No | No | No | Yes |
| 15 | Flat `EUR_USD` plus open `EUR_USD` | `CONFLICT` | No | None | No | Empty | No | No | No | Yes |
| 16 | Missing `tradeIDs` | `COMPLETE_NONEMPTY` | Yes | Replaced | Yes | Not created | Observation with empty trade ids | No | No | No |
| 17 | `FOO_BAR` | `COMPLETE_NONEMPTY` | Yes | Replaced | Yes | Not created | Observation-only | No | No | No |
| 18 | `RuntimeError` | `REQUEST_FAILED` | No | Kept | No | Kept | Kept | No | No | Yes |
| 19 | `TimeoutError` with `OANDA_MAX_RETRIES=1` | `REQUEST_FAILED` | No | Kept | No | Kept | Kept | No | No | Yes |
| 20 | Body `None` | `MALFORMED` | No | Kept | No | Kept | Kept | No | No | Yes |
| 21 | Older valid `EUR_USD` returns after newer valid `GBP_USD` | Newer `COMPLETE_NONEMPTY`; older `STALE` | Newer only | Older not written | Newer only | Not created | Newer instrument | No | No | Stale error on the older cycle |
| 22 | Valid then `{}` | Second is `INCOMPLETE` | No on the second | First book kept | No on the second | Live row kept | Unchanged | No | No | Yes |
| 23 | Valid nonempty then `positions: []` with `auto_fix` | Second is `COMPLETE_EMPTY` | Yes | Replaced with empty | Yes | Permitted live row removed | Not a management grant | Yes, existing disappear path | No `PositionClose` | No on the empty cycle |
| 24 | Valid then malformed | `MALFORMED` | No | Kept | No | Kept | Kept | No | No | Yes |
| 25 | Malformed then valid | Second is `COMPLETE_NONEMPTY` | Yes on the second | First never published | Yes on the second | Not created | Observation-only | No | No | First cycle only |
| Extra | Missing API and account id | `UNKNOWN` | No | Kept | No | Kept | No | No | No | Yes, message contains `unavailable` |

Case 23 is the known unsafe permitted-live behaviour. The snapshot is structurally complete. The local drop is not evidence that a bot close succeeded.

## Destructive regression

| Setup | Invalid evidence | Disappear | Delete or resize | Ownership change | `PositionClose` | Broker-flat class |
| --- | --- | --- | --- | --- | --- | --- |
| Permitted live | Missing key | No | No | No | No | No, class `INCOMPLETE` |
| Permitted live | Malformed positions | No | No | No | No | No |
| Permitted live | Request failure | No | No | No | No | No |
| Permitted live | Older empty after newer nonempty | No | No | No | No | Older classified `STALE` |
| Permitted live | Both sides | No | No | No | No | No, class `CONFLICT` |
| Permitted live | Valid `[]` and `auto_fix` | Yes | Local row removed | Row is removed, not promoted | No | `COMPLETE_EMPTY`, not a close confirmation |
| Observation-only | `{}`, null, string | No | No | Flag stays true | No | No |
| Paper | Those invalid bodies | No | Units unchanged | Paper remains permitted | No | No |
| Paper | Valid broker position | No | Paper units unchanged | Observation recorded separately | No | `COMPLETE_NONEMPTY` |
| Broker discovery | Valid nonempty | No | Not placed in `positions` | `observation_only` true | No | `COMPLETE_NONEMPTY` |

R.68 ownership still holds on these rows: `position_management_permitted` is false for the observation and true only for the paper or permitted live row that was already local.
