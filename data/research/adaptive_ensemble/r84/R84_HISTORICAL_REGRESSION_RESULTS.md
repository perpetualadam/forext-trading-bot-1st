# R.84 historical regression results

Historical files were not modified.

| Suite | Previous | This stage | Class |
| --- | --- | --- | --- |
| R.84 | New | 12 passed | Executed |
| R.83 | 14 passed | 13 passed, 1 failed | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.82 | 19 passed | 18 passed, 1 failed | `OBSOLETE_BEHAVIOURAL_EXPECTATION` |
| R.81 | 16 passed | 16 passed | Preserved |
| R.80 | 17 passed | 17 passed | Preserved |
| R.79 | 17 passed | 17 passed | Preserved |
| R.78 | 21 passed | 21 passed | Preserved |
| R.77 atomic | 82/2/3 of 87 | Same | `PRE_EXISTING_FAILURE` |
| R.77 journal | 0/1/1 of 2 | Same | `OBSOLETE_BEHAVIOURAL_EXPECTATION` from earlier recovery fencing, unchanged |
| R.76 | 64/6/2 of 72 | Same | `PRE_EXISTING_FAILURE` |
| R.75 | 10/3 of 13 | Same | `PRE_EXISTING_FAILURE` |
| R.74 operational | 3/6 of 9 | Same | `PRE_EXISTING_FAILURE` |
| R.74 journal | 20 passed | 20 passed | Preserved |
| R.73 | 8/21/2 of 31 | Same | `PRE_EXISTING_FAILURE` |
| R.72 | 36/1 of 37 | Same | `PRE_EXISTING_FAILURE` |
| R.71 | 8 passed | 8 passed | Preserved |
| R.70 | 25/1 of 26 | Same | `PRE_EXISTING_FAILURE` |
| R.69 | 44/3/0/1 of 48 | Same | `PRE_EXISTING_FAILURE` |
| R.68 | 27/2/1/1 of 31 | Same | `PRE_EXISTING_FAILURE` |

## The two new failures

R.83 `test_13_closed_unit_contract`, line 646, and R.82 `test_16_unit_validation_matrix`, line 648, execute:

`self._apply(self._body("-100", direction_units="-100"))`

and expect `CloseReadError`. The body is a BUY fill of `"-100"` with `tradesClosed[].units="-100"` and requested units 1,000. Under the corrected contract that is a 100-unit signed reduction, so the call returns a partial confirmation instead of raising.

The official full-close example uses that same sign pair. The replacement behaviour is `test_02` in the R.84 suite: requested 100, signed `"-100"`, `CLOSE_FULLY_CONFIRMED`, remaining 0. A negative TradeReduce beside a positive fill still raises `negative_closed_units`, which is `test_05`.

The positive 999, 1,000, zero, and overfill assertions in those same historical tests ran before the failing line and passed. The historical tests were not edited and are not counted as passing.
