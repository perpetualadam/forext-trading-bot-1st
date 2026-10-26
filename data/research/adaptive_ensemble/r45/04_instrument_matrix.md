# R.45 six-instrument contract matrix

Retrieved 2026-10-21, about 15:59 UTC. Effective dates `UNKNOWN`. A public name is not account permission. CFD availability is not spread-bet availability.

The spread-betting page says forex spread betting is offered on more than 65 pairs and gives an indicative EUR/USD spread "from 0.6 pips". It does not list AUD_USD, USD_CAD, USD_CHF, or USD_JPY. GBP_USD is not given its own spread. The retail margin-rate URL did not render a per-instrument card. Major versus non-major is not assigned to these six on the retrieved pages. The worked margin examples say their rates may not be current.

Shared published items, with scope:

- FX session under Forex CFDs: Sunday 17:05 to Friday 16:59 New York, six-minute break, for all FX except TRY. These six are not TRY pairs. Spread-bet hours are not given pair by pair.
- Retail class caps, if the account is retail and the pair is in that class: major forex 30:1 and 3.33%; non-major forex 20:1 and 5%. Which class each pair is in was not on the page.
- Financing admin fee for "other" FX pairs, which is the row left after TRY and the named European and emerging pairs: 1.00% annual, plus a daily tom-next market rate. The full daily rate was not retrieved.
- Home-currency conversion is required when the quote is not the account currency. All six quotes are USD, CAD, CHF, or JPY, so a GBP home currency would need conversion. That does not prove the home currency is GBP.
- GSLO minimum distance and premium are "displayed on the ticket". No numeric premium was published for these pairs. The GSLO page scopes the product to CFDs, while the spread-betting page says GSLOs are available on forex.

| Instrument | Spread-bet availability on the retrieved pages | Pip or point text | Minimum size and increment | Retail margin card | Stops | Financing | Conversion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EUR_USD | Indicative "from 0.6 pips" on the spread-betting page. Not a pair list and not an executable spread. | Margin examples move EUR/USD by amounts they call pips, at 0.0001 per pip in the arithmetic. Not a contract definition. | Not published | Not rendered. Examples elsewhere use 3.33333% as a hypothetical EUR/GBP rate, including one EUR/USD illustration. | Standard stop can slip. GSLO distance and premium not published for this pair. | FX formula and Wednesday triple rule. Daily rate not retrieved. | Needed if home currency is not USD. |
| GBP_USD | Not named, except as a conversion pair in a GBP-account EUR/USD example. | Not defined on these pages. | Not published | Not rendered | Same GSLO limit | Same FX rule | Needed if home currency is not USD. |
| AUD_USD | Not named | Not defined | Not published | Not rendered | Same | Same | Needed if home currency is not USD. |
| USD_CAD | Not named | Not defined | Not published | Not rendered | Same | Same | Needed if home currency is not CAD. |
| USD_CHF | Not named | Not defined | Not published | Not rendered | Same | Same | Needed if home currency is not CHF. |
| USD_JPY | Not named | Not defined. No retrieved example shows 0.01 as a yen pip. | Not published | Not rendered | Same | Same | Needed if home currency is not JPY. |

Price precision of 5 and 3 decimals remains a local code convention. These pages do not publish it. Trading hours for a spread bet on each pair remain `ACCOUNT_SPECIFIC_VERIFICATION_REQUIRED` even though a CFD FX session was published for non-TRY FX.
