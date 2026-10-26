# STAGE R.52 — ISOLATED OANDA LIVE-SESSION ENTRY POINT PREPARATION REPORT

Classification: `R52_LIVE_SESSION_ENTRY_PREPARED`

This classification means the entry point exists, the HTTPS factory is isolated, and the synthetic tests pass. It does not mean the live account is connected or verified.

## Branch and HEAD

- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`

## Preservation

The dirty working tree was left dirty. Operational bytes match the pins carried from R.51. The R.51 adapter hash is `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef`, matching the required pin. R.24–R.51 files were not edited. Source text still shows the six strategies inactive, the quant stub returning `quant_stub_removed`, and unverified RL returning `UNAVAILABLE`. Research lifecycle code remains absent from `bot_loop.py` and `ai_ensemble.py`. The preflight did not import `forex_bot.config`, `forex_bot.oanda_client`, or a strategy module.

## Changed files

New files are only under `data/research/adaptive_ensemble/r52/`.

- Entry point SHA-256: `59cb2fab00a0a1ea67c26261571498f623e8610a8e4e55ae64ac27a3a750ac56`
- The full inventory is `13_changed_files.json`, written after this report.

Production source, configuration, account state, strategy flags, risk limits, `MAX_POSITION_UNITS`, `MIN_STOP_DISTANCE_PRICE`, the 1.35 fallback, and the R.42 range rule were not edited.

## Credentials and network

No credentials were accessed. No account identifier was read. No DNS lookup or HTTP request occurred.

## HTTPS factory

`open_prepared_connection` prepares host `api-fxtrade.oanda.com`, port 443, a five-second timeout, and certificate-verified TLS. It refuses the real HTTPS client class and any subclass. `launch` does not call it. `live_session` raises `R52_LIVE_TRANSPORT_DISABLED` before any connection. Proxy environment variables do not change the host or port.

## Tests

Attempt 1: 12 passed, 0 failed. No correction was required. The 32 behavioural checks are in `07_security_tests.md`. Default execution prints `R52 entry point is disabled. No credential prompt. No network connection.` and exits.

## Sanitised output

`06_synthetic_output.json` is labelled `SYNTHETIC_TEST_ONLY`. It records two calls, instruments then pricing, pip-location spreads, separate conversion factors, and `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`. The historical ticket and financing panel stay in their own sections with `api_confirmation` NO. No executable size is present.

## Manual procedure

`09_manual_procedure.md`. It contains the two hash checks and the disabled command. It does not contain a live execution command.

## Remaining blockers

Broker token permission is `UNKNOWN`. The stake map and the account home currency remain unverified by these two routes. Credential entry and the live client class are prepared and unreachable from normal execution. A live session needs a new written approval and a new hash.

## Future approval boundary

Do not begin R.53. The next approval, after review of this report and `09_manual_procedure.md`, would be one Start-menu session of the two GET requests, with a newly hashed entry point.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
