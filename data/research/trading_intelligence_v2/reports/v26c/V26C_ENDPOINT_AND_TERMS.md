# Endpoint and terms — public review 2026-10-27

`ENDPOINT_SUPPORT_UNVERIFIED`

The official [development guide](https://developer.oanda.com/rest-live-v20/development-guide/)
identifies `api-fxtrade.oanda.com` as the live REST host. The legacy official
[OpenAPI 3.0.25](https://raw.githubusercontent.com/oanda/v20-openapi/master/yaml/v20.yaml)
contains the non-account instrument candle route and says to omit count when
both temporal bounds are supplied. That establishes legacy documentation,
not current service availability or precise boundary semantics.

The [instrument endpoint page](https://developer.oanda.com/rest-live-v20/instrument-ep/)
returned HTTP 404 during public-document retrieval. The current
[pricing page](https://developer.oanda.com/rest-live-v20/pricing-ep/)
documents account-specific latest candles. It is not a substitute for the
requested historical route. No API-host probe was made.

`USAGE_PERMISSION_NOT_FULLY_ESTABLISHED`

The public [OANDA Europe Limited technology agreement, April 2026](https://legal.oanda.com/?code=api_licence_agreement&language=en)
is relevant to the user's stated UK division. Sections 4.1–4.3 condition personal
use, copying and disclosure. Section 18.6 describes internal research/analysis;
18.1–18.2 restrict third-party disclosure and retransmission. This supports a
conditional internal-research interpretation, not blanket permission for
multi-year acquisition, indefinite retention or publication of derived metrics.
The applicable individual agreement/version and any supplemental market-data
licence were not accessed. These public terms do not conclusively establish
all intended rights. No raw prices or derived research results are published here.

## Questions prepared for provider review; not sent

1. Is `GET /v3/instruments/EUR_USD/candles` supported on the live REST host for
   OEL UK clients? Please identify current documentation and historical limits.
2. For M5 MBA, from `2026-09-02T10:00:00Z`, to `2026-09-02T10:49:59Z`,
   includeFirst=true, smooth=false and no count, are bounds applied to candle
   starts, candle completion, or another rule? What completeness is promised?
3. Which OEL provisions permit personal historical research, quantitative
   backtesting, private strategy evaluation and local multi-year candle storage?
   What retention, copying, attribution and deletion obligations apply?
4. May aggregate derived metrics be published without underlying prices or
   reconstructable rate data? Is additional written permission required?

No support contact, form submission, private agreement access or permission
inference from API connectivity occurred. These findings are not legal clearance.
