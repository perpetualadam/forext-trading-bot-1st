# STAGE R.50 — FINAL OFFLINE OANDA READ-ONLY CONNECTOR IMPLEMENTATION AND TESTING REPORT

Classification: `R50_OFFLINE_READONLY_CONNECTOR_COMPLETED`

This classification means the synthetic workflow runs, the security tests pass, and the normal launch stays network-disabled. It does not mean that OANDA connectivity, authentication, or account compatibility has been verified.

## Branch and HEAD

- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`

## Preservation

The working tree was already dirty and was left dirty. No earlier stage was edited. Operational source hashes match the pins recorded through R.49, including `bot_loop.py`, `strategy_meta.py`, `ai_ensemble.py`, `rl_agent.py`, `oanda_client.py`, and the R.42 lifecycle files. The preflight read those files as text. It did not import `forex_bot.config`, `forex_bot.oanda_client`, or a strategy module.

Source text still shows the six strategies starting inactive, the quant stub returning `quant_stub_removed`, and the RL agent returning `UNAVAILABLE` while its policy is not verified. `bot_loop.py` and `ai_ensemble.py` do not reference the research lifecycle.

R.24 through R.49 evidence files are present. R.48 and R.49 were not modified.

## Changed files

New files are only under `data/research/adaptive_ensemble/r50/`. The inventory and hashes are in `13_changed_files.json`, written after this report. Production source, production configuration, account state, strategy flags, risk limits, the GBP 1.35 fallback, and the R.42 range rule were not edited.

## Credentials and network

No credential was accessed. No account identifier was read from the environment, from `.env`, or from a Windows credential store. No DNS lookup or HTTP request was made. The synthetic token and synthetic account identifier stayed in test memory. They are absent from the written matrix and from exception text.

## Synthetic end-to-end requests

The injected transport received exactly two GET calls: account instruments, then account pricing with `includeHomeConversions=true`. Both used `api-fxtrade.oanda.com` and the six-name filter. The sanitised matrix is labelled `SYNTHETIC_TEST_ONLY`. USD_JPY spread uses pip location -2. Removed conversion factors stay `NOT_RETURNED` and are not replaced with 1.35.

## Security tests

Attempt 1: 25 passed, 1 failed. The failure caught a placeholder conversion dictionary being labelled present. The assertion was kept.

Attempt 2: 38 passed, covering the R.50 suite and the existing R.48 and R.49 offline tests. The numbered checks are in `04_security_tests.md`.

The broader application suite was skipped because importing it reads the OANDA access token. R.28 PostgreSQL scripts were not run.

## Sanitised findings

All six synthetic rows carry pip location, trade-unit precision, a minimum size, a margin rate, bid, ask, a pip-location spread, conversion factors, stop fields, and financing fields. Eligibility evidence is `SYNTHETIC_TEST_ONLY`. Remaining GBP sizing is `UNKNOWN` on every row. The historical ticket and the user-reported financing panel stay in separate sections and are not treated as API confirmation.

## Remaining gaps

There is no HTTPS client. Real credential entry is not implemented. Broker-enforced read-only permission is `UNKNOWN`. The spread-bet stake map, the unrounded GBP pip value, and the margin class remain unresolved. No executable size was calculated.

## Proposed Windows procedure

Run `python -B "data\research\adaptive_ensemble\r50\connector.py"` from a Start-menu window if the offline message is needed. The program prints that live verification remains unauthorised, asks for nothing, and exits. Flags and phrases do not enable a connection. Do not type a token into Cursor. The full steps are in `09_manual_procedure.md`.

## Recommended next authorisation boundary

Do not begin R.51. A later stage would need a separate authorisation for one reviewed live HTTPS send of the two GET templates, outside Cursor, with sanitised output only. That future boundary would still exclude orders, candles, backtests, strategy activation, deployment, and rollback.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
