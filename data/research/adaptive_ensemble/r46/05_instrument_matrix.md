# R.46 six-instrument contract matrix

The screen did not list enabled instruments. A local default name is not account permission. No new pairs are added. Public effective dates remain `UNKNOWN`. Retrieval of the public pages was R.45, 2026-10-21 about 15:59 UTC.

Shared rows:

| Field | All six | Classification |
| --- | --- | --- |
| Account eligibility | Not displayed | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` |
| Minimum size and increment | Not in the retrieved text and not on the screen | `UNKNOWN` |
| Stake versus units | Code uses units. Public pages use units. No stake map. | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` |
| GBP value of one pip | Not defined | `UNKNOWN` |
| GBP conversion | Candidate public method is the v20 1.0% mid markup when the quote is not GBP. Code does not implement it. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` for the candidate. `CONFLICTING_EVIDENCE` in the code. |
| Margin rate | Class caps exist. The pair's class and this account's rate do not. | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` |
| Closeout | Candidate is the v20 100% full liquidation. The bot does not apply it. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |
| Stops | A normal stop can slip. Guaranteed-stop distance and premium are not published for these pairs. | `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` |
| Financing | FX formula and Wednesday triple are candidates. The day's rate was not retrieved. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` for the formula. `UNKNOWN` for the rate. |
| Fees | Commission-free is a spread-bet marketing sentence. The 1.0% conversion is a separate candidate charge. | `PUBLICLY_DOCUMENTED_WITH_SCOPE_LIMITATIONS` |

| Instrument | Quote | Code pip | Code price format | Public spread-bet evidence | Conversion if home currency is the reported GBP |
| --- | --- | --- | --- | --- | --- |
| EUR_USD | USD | 0.0001 | 5 decimals | Named on the spread-betting page as "from 0.6 pips". Not an executable spread and not eligibility. | Quote is not GBP. Candidate conversion applies. Unverified on a fill. |
| GBP_USD | USD | 0.0001 | 5 decimals | Not named as a spread-bet instrument. Appears as a conversion pair in a GBP-account example. | Quote is not GBP. The pair is also the conversion instrument in that example. Eligibility is still unverified. |
| AUD_USD | USD | 0.0001 | 5 decimals | Not named | Quote is not GBP. |
| USD_CAD | CAD | 0.0001 | 5 decimals | Not named | Quote is not GBP. |
| USD_CHF | CHF | 0.0001 | 5 decimals | Not named | Quote is not GBP. |
| USD_JPY | JPY | 0.01 | 3 decimals | Not named. No retrieved example defines a yen pip as 0.01. The 0.01 and 3-decimal figures are code conventions. | Quote is not GBP. |

Code pip and price format are `LOCALLY_VERIFIED_IMPLEMENTATION`. They are not broker precision. For a reported GBP account, `oanda_account_adapter` returns `exposure_conversion_missing` for every row, because each quote differs from GBP. That is fail-closed behaviour, not a conversion.
