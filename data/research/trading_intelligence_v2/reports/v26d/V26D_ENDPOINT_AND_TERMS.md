# Public endpoint/terms review — 2026-10-27

`ENDPOINT_SUPPORT_UNVERIFIED`

The official [instrument endpoint page](https://developer.oanda.com/rest-live-v20/instrument-ep/)
still returns 404. The current [pricing documentation](https://developer.oanda.com/rest-live-v20/pricing-ep/)
describes an account-specific latest-candle route, not proof of the requested
non-account historical route. The official legacy [OpenAPI 3.0.25](https://raw.githubusercontent.com/oanda/v20-openapi/master/yaml/v20.yaml)
contains the non-account route, which does not establish current LIVE support.
No API-host probe or account-specific substitution occurred.

`USAGE_PERMISSION_NOT_FULLY_ESTABLISHED`

The public [OANDA Europe Limited technology agreement, April 2026](https://legal.oanda.com/?code=api_licence_agreement&language=en)
conditions use/copying/disclosure in section 4 and discusses internal research
and third-party restrictions in section 18. It does not, by itself, establish
all intended multi-year retrieval, retention and derived-publication rights for
the user's applicable account agreement. No private documents or credentials
were accessed. General API access is not unrestricted data-use permission.

Unsent provider questions remain:

1. Is the non-account EUR_USD candle route currently supported for OEL UK LIVE,
   and where are its current limits and boundary/completeness rules documented?
2. For the preserved M5 MBA September interval, do temporal bounds select candle
   starts or completion times? Is count omitted with both bounds?
3. What terms permit private multi-year backtesting/local retention, for how
   long, and may aggregate derived metrics be published without underlying rates?

No support contact or form submission. Documentation uncertainty cannot activate
the disabled entry or produce a real grant.
