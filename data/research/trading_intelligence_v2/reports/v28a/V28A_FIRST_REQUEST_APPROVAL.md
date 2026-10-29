# V2.8A first-request approval preparation

LOCAL IMPLEMENTATION VERIFIED; PUBLICATION AND EXECUTION NOT APPROVED. Currently authorised HTTP attempts: ZERO.

First request ID: 109f365402a844adacad671d62e4458f.

GET https://api-fxtrade.oanda.com/v3/instruments/EUR_USD/candles

```
from=2024-08-05T00:00:00+00:00
to=2024-08-08T11:19:59+00:00
granularity=M5
price=MBA
smooth=false
includeFirst=true
```

Count omitted; at most 1,000 completed candles; ONE HTTP attempt after separate approval. No retries, redirects, proxy, pagination, fallback or account endpoint. Protected destination C:\TradingResearchData\OANDA\sessions\109f365402a844adacad671d62e4458f. Preserve 15/120/15-second limits.

Local candidate source seal: 34939a3db7ccd4dbb1b851ac6fb96c0ceba0b054b60dc65bd58f3248f2fd68d6. The namespace contains only request and binding metadata. No grant, journal, worker claim, result or authenticated data exists.

Future command from repository root, ONLY after publication approval/verification and separate first-GET approval:

```powershell
python -I -S -B data\research\trading_intelligence_v2\historical_session_entry.py --pilot-window=1
```

Exact rights attestation:

```
I CONFIRM ACCOUNT ENTITLEMENT AND PRIVATE RESEARCH RETENTION
```

Exact endpoint acknowledgement:

```
I ACCEPT ONE NON-ACCOUNT ENDPOINT CONNECTIVITY CHECK
```

Exact final confirmation:

```
CONFIRM ONE HISTORICAL EUR_USD REQUEST 34939a3db7cc 109f365402a844adacad671d62e4458f
```

Applicable account/private-research retention and derived-use permissions for these August dates must be truthfully affirmed; prior limited September permission does not imply expansion rights. Non-account endpoint acceptance on the old request does not guarantee support for every interval. No account substitution or bypass if refused.

Requests two and three require their OWN separate exact source/session approvals; earlier requests must be durably successful and hash-verified. Success never automatically approves the next. Any failed or ambiguous outcome stops the pilot. No real command was invoked in preparation. Production NO-GO.
