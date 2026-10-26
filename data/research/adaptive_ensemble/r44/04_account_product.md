# R.44 account product and jurisdiction

No claim below is `ACCOUNT_VERIFIED`. Intended configuration and code defaults are not account status.

| Claim | Class | Source | What it proves | What it does not prove | Blocks |
| --- | --- | --- | --- | --- | --- |
| The code's broker target is OANDA v20, with practice host `api-fxpractice.oanda.com` and live host `api-fxtrade.oanda.com`. | `LOCALLY_VERIFIED_IMPLEMENTATION` | `forex_bot/oanda_client.py` `official_rest_host`, `symbols.py` spot-FX name comment | The repository selects one of those two hosts from `TRADING_MODE`. | That this user has an account, or which host it uses. | Trading and any live check |
| Default `TRADING_MODE` is `practice` when the environment variable is unset. | `ASSUMPTION_ONLY` | `forex_bot/config.py` `Config.TRADING_MODE` | The source default. The live environment value was not read. | Practice versus live for this account. | Yes |
| A past G.3 candle plan was labelled `environment: live` and host `api-fxtrade.oanda.com`. | `DOCUMENTED_BUT_ACCOUNT_UNVERIFIED` | `data/research/adaptive_ensemble/g3/request_plan.json`, cited by R.43 | A previous research plan named a live candle endpoint. `account_endpoints` was false. | Current mode, product type, or permission to trade. | Does not by itself authorise trading |
| Practice default and the G.3 live label disagree. | `CONFLICTING_EVIDENCE` | `config.py` and the G.3 plan | Two local artefacts name different environments. | Which one is current. | Yes, until a later authorised check names the environment |
| Account currency is GBP. | `CONFLICTING_EVIDENCE` | `oanda_client.py` comment says "e.g. GBP". `trading.py` `quote_pnl_to_account_ccy` says "approximate account USD". Shadow code converts into GBP. R.27 fixture currency was USD. | The repository does not have one currency assumption. | The account currency. | Yes |
| The product is a GBP spread-betting account. | `UNKNOWN` | Research briefs state the intention. `symbols.py` describes "spot FX" instrument names. | Intention and a spot-FX code comment. | Product type, jurisdiction, or eligibility. UK residence was not used as evidence. | Yes |
| Jurisdiction and product restrictions. | `UNKNOWN` | No approved local source | Nothing. | Nothing about the legal product. | Yes |
| Instrument permissions for the six names. | `UNKNOWN` | Local files exist. No account instrument list was read. | Research files use those names. | That the account can trade them, or that a spread-bet identifier matches `EUR_USD`. | Yes |
| Shadow starting NAV is 97.15 GBP. | `ASSUMPTION_ONLY` | `forex_bot/shadow/config.py` `starting_nav_gbp`, label `SIMULATED_SHADOW_NOT_BROKER` | A shadow default. The same figure was named in the R.43 brief. | Current NAV, balance, or a spread. | The figure must not be used as a cost or as equity |
| Default sizing equity is 10000. | `ASSUMPTION_ONLY` | `Config.BASE_BALANCE` | A source default. | Account equity. | Yes if used as a real balance |
