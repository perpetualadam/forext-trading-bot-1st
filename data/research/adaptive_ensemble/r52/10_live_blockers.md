# Live execution blockers

- `launch` never calls the factory, the credential prompt, or `live_session`.
- `live_session` raises `R52_LIVE_TRANSPORT_DISABLED` before any other work.
- `enable_live` raises the same code for every argument.
- `prompt_for_credentials` raises the same code unless two readers are supplied by the caller. Normal execution does not supply them.
- `open_prepared_connection` refuses `http.client.HTTPSConnection` and any subclass before construction.
- `read_bounded` refuses a live client object.
- `run_synthetic` refuses the live client class before the R.51 adapter is asked to run.
- No command-line flag, environment variable, confirmation phrase, or boolean is read as an on switch.
- The R.51 adapter pin must match. A hash mismatch stops the entry point.
- Account home currency is `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`.
- Broker token permission is `UNKNOWN`.
- No executable size is calculated.

Removing the live-class refusal would be a new review, with a new hash. This stage does not do that.
