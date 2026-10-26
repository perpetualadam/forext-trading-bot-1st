# GBP home-currency limitation

The intended account is the user-reported OANDA live v20 GBP spread-betting account from R.46. That classification remains separate evidence.

The two permitted responses do not carry an authoritative account home-currency field. A home-conversion block can name a currency and still leave the account currency unknown. In the synthetic fixture that named currency is the pair's conversion currency. A test that planted GBP in that field still received:

`ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`

`quoted_conversion_currency_is_account_home` is NO.

A conversion factor does not prove the spread-betting stake-to-unit convention. `stake_settlement` stays `UNKNOWN`.

No account-summary, balance, or account-discovery endpoint is added to fill this gap.
