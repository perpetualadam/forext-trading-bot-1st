# STAGE R.51 — ONE-TIME OANDA READ-ONLY API SESSION PREPARATION REPORT

Classification: `R51_READONLY_HTTPS_ADAPTER_PREPARED`

This classification means the isolated adapter exists, the synthetic tests pass, and the normal launch stays network-disabled. It does not mean the account is connected or verified.

## Branch and HEAD

- Branch: `main`
- HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Project root: `C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st`

## Preservation

The dirty working tree was left dirty. Operational bytes match the pins carried from R.50, including `bot_loop.py`, `strategy_meta.py`, `ai_ensemble.py`, `rl_agent.py`, `oanda_client.py`, the R.42 lifecycle files, and `r50/connector.py`. Source text still shows the six strategies inactive, the quant stub returning `quant_stub_removed`, and unverified RL returning `UNAVAILABLE`. Research lifecycle code is absent from `bot_loop.py` and `ai_ensemble.py`. R.24–R.50 evidence is intact. The preflight did not import `forex_bot.config`, `forex_bot.oanda_client`, or a strategy module.

## Changed files

New files are only under `data/research/adaptive_ensemble/r51/`. The adapter SHA-256 is `e08652cbd3b3b352fd7a3908288cb4a7e48a56ab7d17b429d2688698d8848cef`. The full inventory is `13_changed_files.json`, written after this report. Production source, configuration, account state, risk limits, strategy flags, `MAX_POSITION_UNITS`, `MIN_STOP_DISTANCE_PRICE`, the 1.35 fallback, and the R.42 range rule were not edited.

## Credentials and network

No credentials were accessed. No account identifier was read from the environment, from `.env`, or from a credential store. No DNS lookup or HTTP request occurred. The default command prints that live verification remains unauthorised and exits. Passing the real HTTPS class, a flag, a phrase, or `blocked_factory` raises `R51_LIVE_TRANSPORT_DISABLED` before a connection is constructed.

## Adapter

`https_adapter.py` builds a certificate-verified TLS context, accepts only the two GET templates, and performs the exchange through an injected factory. `run_offline` drives the R.50 two-call workflow with a budget of two sequential calls. The real connection factory is not implemented.

## Tests

Attempt 1: 11 passed, 0 failed. No correction was required. The R.50 suite still passes: 26 passed. Details are in `12_test_results.md` and `04_tls_enforcement.md`.

## GBP home currency

The two permitted responses do not establish the account home currency. The synthetic session records `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`. A planted conversion currency of GBP stayed a quoted conversion currency, with `quoted_conversion_currency_is_account_home` set to NO. The R.46 GBP screen remains separate evidence. No account-summary endpoint was added.

## Manual procedure

`09_manual_procedure.md`. It includes the hash check and the disabled command. It does not contain a command that authenticates.

## Remaining blockers

Broker token permission is `UNKNOWN`. The stake map and an executable size are unresolved. A live factory and a real credential prompt are not in this stage. Further risks are in `14_risks.md`.

## Next approval boundary

Do not begin R.52. The next step is your review of this report and of `09_manual_procedure.md`. Only a later written approval can add the one connection factory for those two GET requests.

PRODUCTION DEPLOYMENT: NO-GO.
PRACTICE ORDERS: NOT AUTHORISED.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
