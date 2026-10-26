# R.71 Multi-Pair Audit

## Default universe

`DEFAULT_FOREX_SYMBOLS` is EUR_USD, GBP_USD, USD_JPY, AUD_USD, USD_CAD, and USD_CHF (`symbols.py` 12–19). `configured_symbols` parses `FOREX_SYMBOLS` and falls back to that list (82–84). `run_bot` iterates `Config.SYMBOLS` (`bot_loop.py` 4424). This audit did not import the real config module, so the value inside an unopened `.env` was not read. The code default, when the variable is blank, is the six names.

## What each level means

| Level | Six names |
| --- | --- |
| Mentioned in research | Yes, including adaptive-ensemble pair lists |
| Accepted by the parser | Yes. `AAA_BBB` is valid. A slash or hyphen is normalised |
| Pip size | JPY quote 0.01, the other five 0.0001 |
| Paper spread table | All six have an entry. GBP_USD is 0.00015. The others are 0.0001 (`trading.py` 73–80) |
| Session windows | EUR_USD and GBP_USD have explicit windows in `session_rules.py`. Other names use the module's fallback. This audit did not execute the session clock |
| Signal selection | The selector is behind the entry block |
| Risk formula | Reachable only as a direct function call. The entry call is blocked |
| New-order eligibility | Blocked for every pair |
| Backtest coverage | Research files name the six pairs. That is not an operational backtest result |

A name in the default list is not an enabled live order. Iteration of the list is connected. Order placement is not.

## Pair-specific behaviour that is real

- USD_JPY pip and stop distance differ from the majors. The test showed 0.20 versus 0.0020 for a 20-pip stop.
- USD-base symbols use the divide-by-mid risk branch. EUR_USD, GBP_USD, and AUD_USD do not.
- USD_CAD and USD_CHF are USD-base for that branch and JPY-unlike for pip size.
