# R.71 Test Coverage and Results

## Suites inspected and not run

`tests/conftest.py` imports live-safety and strategy helpers. Those imports load the operational config path. Pytest was not invoked.

`tests/test_profit_protection.py` targets the 67 percent trigger, ratchet, SELL side, restart seeding, and retry. Its own imports are `positions` and `profit_protection`, which do not load config. Running it through pytest would still load `conftest.py`. It was left unexecuted. Its assertions were not edited.

Broker, database, and live-order tests under `tests/` are `NOT_VERIFIED` for this audit. They were not weakened.

Prior R.68, R.69, and R.70 results are historical evidence for ownership and snapshot behaviour. They are not new R.71 broker tests. This audit re-checked the ownership predicate and the snapshot classifier with synthetic inputs.

## What ran

```text
python -B data/research/adaptive_ensemble/r71/poc/test_r71_readonly_calculations.py
```

Windows CPython 3.13.5: 8 tests, 0 failures, 0.003s.

The file imports the R.69 isolation harness before `forex_bot`. The harness recorded no `load_dotenv` and no `socket.connect`.

| Check | Result |
| --- | --- |
| Default 0.67, ATR 14, multiplier 0.5, fallback 4 | Passed |
| EUR_USD pip 0.0001 and USD_JPY pip 0.01 | Passed |
| 30-pip target activates at 20.1 pips for BUY and SELL | Passed |
| A SELL marked with a higher price is negative profit | Passed |
| ATR 0.0010 becomes 5 pips of giveback, not the 4-pip fallback | Passed |
| Missing ATR uses 4 pips | Passed |
| A larger later ATR does not lower the stored exit | Passed |
| Observation is not management-permitted | Passed |
| `{}` is `INCOMPLETE`; `{"positions":[]}` is `COMPLETE_EMPTY` | Passed |
| EUR_USD 1 percent of 10,000 at a 0.002 stop is 50,000 units and 100 quote risk | Passed |

## Negative controls

The tests fail if the pip sizes are swapped, if 67 percent of 30 pips is not 20.1, if the ATR multiplier is not 0.5, if the ratchet stores the looser threshold, if an observation is permitted, or if a missing positions key is classified as an empty book. They do not execute a local close against a broker, so "local close without confirmation" was classified from source rather than reproduced as an order.

## WSL2

The same command failed at `import oandapyV20` inside `reconciliation.py`. `LINUX_INTEGRATION_NOT_VERIFIED`.
