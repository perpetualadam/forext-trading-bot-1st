# R.44 broker-specific blocker register

Trading authorisations are unchanged. Every row blocks live trading. Practice trading is blocked for the same reason: the product and the size rules are unverified. Public documentation could explain a product and still not prove this account has it.

| Blocker | Why it matters | Blocks offline GBP evaluation | Blocks practice | Blocks live | Public docs enough | Needs this account | Needs a later read-only request | Needs further user approval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Product and jurisdiction | Spread-bet, CFD, and spot change the size unit and the charges | Yes | Yes | Yes | No | Yes | Only if the user approves route C | Yes |
| Instrument eligibility | Local names may not be the tradable identifiers | Yes | Yes | Yes | No | Yes | Route C, if approved | Yes |
| Stake versus units | The code sizes in units | Yes | Yes | Yes | A public page can define the product unit, not this account's permission | Yes for the permission | Route C for the account flag | Yes |
| Minimum and increment | An undersized order is rejected | Yes | Yes | Yes | The schedule might be public. Applicability is not. | Yes | Route C if the public page is insufficient | Yes |
| Pip value in GBP | Price pips are not money | Yes | Yes | Yes | Maybe the product definition. Not this account. | Yes | Route C if still unknown | Yes |
| GBP conversion | Three local methods disagree, and the adapter fails closed when the quote is not the account currency | Yes | Yes | Yes | A formula might be public. The charge is not in the files. | Yes | Route C for the account currency and charge | Yes |
| Margin and closeout | Parsed margin is not a limit | Yes for any sized result | Yes | Yes | The general rule might be public | Yes | Route C | Yes |
| Stops and order constraints | No verified minimum distance or guaranteed-stop charge | Yes if the test uses stops | Yes | Yes | Possibly the general rule | Yes | Route C | Yes |
| Overnight financing | Model is `UNAVAILABLE` and a financing ledger row blocks | Yes for holds | Yes | Yes | The schedule might be public | Yes for this account's rate | Route C if the schedule is account-specific | Yes |
| Weekend financing | Candle gaps are known. The charge is not. | Yes for weekend holds | Yes | Yes | Same as overnight | Yes | Same | Yes |
| Fees and current spread | Historical bid/ask are not commission or today's spread | Yes | Yes | Yes | No | Yes for the account schedule | A later quote read is still a broker request | Yes |
| Transaction reconciliation | Parser expects account-currency `pl`. Currency is unverified. | Yes | Yes | Yes | No | Yes | Route C | Yes |
