# Broker evidence contract

Option A is two GET requests: account instruments, then account pricing with `includeHomeConversions=true`, for `EUR_USD`, `GBP_USD`, `AUD_USD`, `USD_CAD`, `USD_CHF`, and `USD_JPY`. This contract does not add a conversion rate. `1.35` stays forbidden. No trading signal and no position size are produced.

## Evidence levels

| Level | Meaning | Option A result |
| --- | --- | --- |
| Response received | The server returned bytes and a status. | A future HTTP 200 would be this level only. |
| Structurally validated | The bytes matched the local field checks. | Possible for the allowlisted fields. |
| Account-specific field observed | A value was copied from that response. | Possible for fields that are actually present. Absence stays `NOT_RETURNED`. |
| Financial interpretation independently verified | A copied value has an agreed meaning for this account's contract. | Not available from these two routes for the items in the second table. |
| Broker-contract question unresolved | The API response does not settle the contract question. | Remains the status for home currency, stake mapping, pip value, financing, token permission, and size. |

HTTP 200 is not account verification. Parser acceptance is not account verification. The label for a future real parse would be `READ_ONLY_RESPONSE_NOT_ACCOUNT_VERIFIED`. `ACCOUNT_VERIFIED` is forbidden. Current B2 output remains `SYNTHETIC_TEST_ONLY` and `NOT_PRODUCED`. Fixtures must not be copied into a broker file if a real field is missing.

## What Option A could show

| Observation | How it would be established | Limit |
| --- | --- | --- |
| Instrument identifiers | Names present in the instruments payload, after unexpected names are rejected. | A missing name is `NOT_RETURNED` or a failed session. It is not filled from a fixture. |
| Pip locations and constraints | `pipLocation`, display precision, minimum trade size, margin rate, and the other allowlisted instrument fields, when present. | A copied minimum or maximum is not an order quantity. `type` `CURRENCY` is not a spread-bet decision. |
| Bid and ask | The first `bids[0].price` and first `asks[0].price` when both are finite and positive and bid is not above ask. | Deeper book levels are not kept. These are not fills. |
| Pricing timestamps | The `time` string when it matches the local pattern. | The pattern does not prove the quote is fresh. See the freshness section. |
| Tradeability | Boolean `tradeable` as returned. | `false` means the quote is not usable. It does not explain why. |
| Quoted spread | Calculated `(ask - bid) / 10**pipLocation` only when that arithmetic is defined. | This is a width from the returned prices, not a broker-published spread and not an executable spread. Pip size must not be hardcoded as `0.0001`. |
| Home-conversion fields | `positiveUnits`, `negativeUnits`, `accountGain`, `accountLoss`, and the quoted `currency`, kept separate. | Missing stays `NOT_RETURNED`. Two currencies are `AMBIGUOUS`. The quoted currency is not the account home currency. |
| Request and validation status | Separate counters for attempts, HTTP 200, and validated responses. | Two attempts are not success. Success requires both responses validated. |

## What Option A cannot settle

| Fact | Status under Option A |
| --- | --- |
| Account home currency | `ACCOUNT_HOME_CURRENCY_API_UNVERIFIED`. These routes have no account-level currency field in the local schema. |
| Spread-bet stake-to-API-unit mapping | `NOT_VERIFIED`. Quantity 1 is not £1 per pip. |
| GBP pip value | `NOT_VERIFIED`. No value is calculated. |
| Financing formula | `NOT_VERIFIED`. A returned long or short rate, if present, is a rate, not a GBP charge. The historical panel stays outside API evidence. |
| Token permissions | `UNKNOWN`. |
| Executable position size | `NOT_CALCULATED`. |
| Strategy profitability | `NOT_ESTABLISHED`. |

## Quote freshness

The B2 timestamp check accepts `YYYY-MM-DDTHH:MM:SS` with optional fractions and either `Z` or a numeric offset. A missing timestamp is `MISSING_TIMESTAMP`. A bad string is `MALFORMED_TIMESTAMP`. A date in 1999 is accepted. There is no `MAX_QUOTE_AGE`. Quote freshness is `NOT_VERIFIED`.

Future policy, still without an invented age limit:

| Case | Treatment |
| --- | --- |
| Missing timestamp | Fail that response. Do not invent a time. |
| Malformed timestamp | Fail that response. |
| Time zone | Accept only `Z` or an explicit numeric offset. Do not treat a bare local clock time as UTC. The broker's clock source is **DOCUMENTATION_VERIFICATION_REQUIRED**. |
| Future-dated timestamp | Record it if the syntax is valid. Mark freshness `NOT_VERIFIED`. Do not use it for a trading decision. |
| Old timestamp | Same. No cutoff is defined, so age is not a pass or a fail. |
| Untradeable | Not a usable quote. No substitute price. |
| Missing bid or ask | Fail that instrument. No fixture price. |
| Several price levels | Keep the first bid and the first ask only, and say the rest were not retained. That is a selection, not the full book. |
| Conflicting conversion currencies | `AMBIGUOUS`. Do not pick one as the home currency. |
| Partial instrument coverage | Do not report the six names as complete. No success file that claims full coverage. |

Because no defensible age threshold is available, quote freshness stays `NOT_VERIFIED` and the prices must not be used as trading inputs.

Option B remains deferred. Its schema is **DOCUMENTATION_VERIFICATION_REQUIRED**. It is not a way to answer the home-currency row in this contract.
