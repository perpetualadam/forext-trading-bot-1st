# R.48 credential-isolation assessment

Classification of this gate: closed. No credential was read, printed, hashed, or stored. No token was requested in chat. No search of `.env`, the process environment, or a credential store was performed.

The production client is not a safe path for this stage. `forex_bot/config.py` assigns `OANDA_ACCESS_TOKEN` from the environment when that module is imported, and `forex_bot/oanda_client.py` can place the process on `https://api-fxtrade.oanda.com` or `https://api-fxpractice.oanda.com`. That client lives in a runtime that also contains order methods. A script that only calls GET does not remove those methods from the same process. R.44–R.47 do not establish that an OANDA personal access token is limited to read-only permission. This stage does not claim that any credential is read-only.

Importing `forex_bot.ai_ensemble` builds the default ensemble and can read other API-key variables. The R.48 preflight did not import it. It confirmed the fail-closed stub from the source text and from the unchanged file hash. It imported `strategy_meta` and `rl_agent` only. `forex_bot.config` and `forex_bot.oanda_client` were not imported. The preflight record shows both as not imported.

A standalone gate is in `readonly_transport.py`. It does not import the production package, does not read the environment, and its `perform_request` function raises `R48_AUTHENTICATED_EXECUTION_BLOCKED` before a connection. `EXECUTION_PERMITTED` is false. That gate is an offline design. It is not an authenticated session.

No separate read-only token was supplied through an approved mechanism. Provisioning one would be a new explicit user action. This stage does not ask for the token, the account identifier, or a change to OANDA security settings.
