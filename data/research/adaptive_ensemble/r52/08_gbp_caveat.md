# GBP home currency and spread-bet caveats

The synthetic rows keep `account_home_currency` at `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`. A quoted conversion currency is copied only as `quoted_conversion_currency`, with `quoted_conversion_currency_is_account_home` set to NO. Instrument type `CURRENCY` does not establish the spread-bet stake map. `stake_settlement` is `UNKNOWN`.

No executable size is calculated. The historical ticket stays in `historical_ticket` with `api_confirmation` NO, `used_as_position_cap` NO, `one_pip_is_zero_risk` NO, and `margin_is_fixed_rate` NO. The financing panel stays in `historical_financing_panel` with `api_confirmation` NO. Those sections are not API fields.

No account-summary endpoint was added.
