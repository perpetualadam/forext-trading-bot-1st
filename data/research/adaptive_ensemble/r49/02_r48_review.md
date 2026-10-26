# R.49 review of the R.48 transport

`data/research/adaptive_ensemble/r48/readonly_transport.py` was read as a research file. It was not changed. Its hash remains `3ef1be4e565b7e2f783931e66e962ba3264f4be551bda2e4cd87f1705bf3b844`.

The transport does not import the production package. It has no HTTP library. `perform_request` raises `R48_AUTHENTICATED_EXECUTION_BLOCKED`. `EXECUTION_PERMITTED` is false. The allowlist is GET on `api-fxtrade.oanda.com` for `/v3/accounts/{accountID}/instruments` and `/v3/accounts/{accountID}/pricing`, limited to the six instrument names. Pricing includes the home-conversion query. Redirects, retries, bodies, and streams are refused. The parser keeps gain and loss factors apart, and positive-unit and negative-unit factors apart.

The R.49 runner loads that file by path. It does not import `forex_bot`.

Importing `forex_bot.config` would read `OANDA_ACCESS_TOKEN` and `OANDA_ACCOUNT_ID` from the environment, and the module also calls `load_dotenv()`, which reads `.env`. Importing `forex_bot.oanda_client` pulls that configuration into a process that also contains order methods. Either import breaks the research boundary. R.49 does not import them.
