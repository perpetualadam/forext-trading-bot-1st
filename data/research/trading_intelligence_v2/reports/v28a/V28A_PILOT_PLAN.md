# V2.8A non-authorising pilot plan

Baseline 95c061bb2411b064be50bd77d058a7b1a665db69. OFFLINE_PREPARATION_ONLY. No authenticated request authorised. Production NO-GO.

Exact common request: LIVE GET https://api-fxtrade.oanda.com/v3/instruments/EUR_USD/candles ; granularity=M5, price=MBA, smooth=false, includeFirst=true. Count omitted. One attempt per independently approved future session; zero retries, redirects, proxies, pagination or fallback. No account-specific endpoint substitution. No automatic progression. Three planned requests, ZERO currently authorised.

1. Proposed ID 109f365402a844adacad671d62e4458f. Half-open [2024-08-05T00:00:00Z, 2024-08-08T11:20:00Z). Query from=2024-08-05T00:00:00+00:00, to=2024-08-08T11:19:59+00:00. Maximum 1,000 completed M5 candles. Specification SHA-256 2242b6d2eef8106607aca2b1b5e13250cf4e2894030e69fc235a70d8a8687fa8.
2. Proposed ID b2e5582e3cd347bd80a02109d7a476c2. Half-open [2024-08-08T11:20:00Z, 2024-08-11T22:40:00Z). Query from=2024-08-08T11:20:00+00:00, to=2024-08-11T22:39:59+00:00. Maximum 1,000 completed M5 candles. Specification SHA-256 19f9431035e71981108dd094ce0a31d56b1a46edd24839f97a6f6aa37c3fac8d.
3. Proposed ID 5d4e7676ab9e4393a4678cfb23274a4c. Half-open [2024-08-11T22:40:00Z, 2024-08-12T00:00:00Z). Query from=2024-08-11T22:40:00+00:00, to=2024-08-11T23:59:59+00:00. Maximum 16 completed M5 candles. Specification SHA-256 f7c34840543aaadc138e0b880f7e4f4126c402e56b1e529d77aa3486ed29e8f5.

All three share local candidate implementation seal 34939a3db7ccd4dbb1b851ac6fb96c0ceba0b054b60dc65bd58f3248f2fd68d6, NOT execution authority. The local source catalogue contains exactly the original request plus these three profiles; no arbitrary spec override or reusable multi-request permit. The source seal was updated for this genuine authority implementation change, not to revive any consumed request. The old seal and all historical state remain preserved. Publication requires separate approval.

Each ID now has its own non-authorising native namespace with request.json and session_binding.json only. No grant, journal, worker claim, result or authenticated data was created. Window dataclasses are frozen; spec properties return fresh copies. Each LIVE grant can be issued only after separate exact terminal attestations and final source/session confirmation. A successful prior session never supplies that proof.

Each proposed destination is C:\TradingResearchData\OANDA\sessions\<its ID>, using existing raw/v26c_https.json, validated/v26c_https.json and manifests/v26c_https.json conventions. Only non-authorising namespace/binding/request metadata was created; no authenticated data file was created. No OneDrive or Git market-data destination. No existing record overwritten.

The 2,016-slot week includes closures; actual candles are not guaranteed (rough weekday estimate 1,440). Missing observations stay missing; no inferred holiday calendar, weekend filling, sorting or duplication repairs. Retain original timestamps, complete flags, decimal lexemes and source hashes. Pilot data alone is not an independent strategy dataset.
