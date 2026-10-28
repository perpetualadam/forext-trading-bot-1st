# First historical GET — proposal only

Command prepared for the separately authorised workflow:

```powershell
python -I -S -B data\research\trading_intelligence_v2\historical_session_entry.py
```

The command currently displays the proposal and refuses with exit 2. Approval
text in chat or typing a confirmation phrase cannot create admission. A separately
reviewed real-session admission mechanism is still absent; this stage does not
change V2.6G's unconditional refusal or create a permit/grant. Do not claim this
command can already retrieve data merely because the frontend tests pass.

Exact proposal, unchanged:

```text
Environment: LIVE
Host: api-fxtrade.oanda.com:443
Method: GET
Path: /v3/instruments/EUR_USD/candles
granularity=M5
price=MBA
smooth=false
includeFirst=true
from=2026-09-02T10:00:00Z
to=2026-09-02T10:49:59Z
count: omitted
Maximum authenticated attempts: 1
Retries: 0; redirects: disabled; proxy: disabled; pagination: disabled
Total acquisition deadline: 15 seconds, including hidden token entry and fencing
Storage: C:\TradingResearchData\OANDA
```

Future admitted behaviour: review the exact screen, confirm
CONFIRM ONE HISTORICAL EUR_USD REQUEST, then enter API token: at a hidden native
Windows terminal prompt after durable reservation. No account ID is requested.
The token must be entered within the remaining work budget (less than fourteen
seconds); timeout consumes the attempt. Nothing is read from .env or production
credential storage. Never paste a token into ChatGPT, argv, reports or Git.

Keep timestamp-boundary ambiguity and actual returned complete count; ten candles
are not guaranteed. Validate/store using existing protected binding, NTFS/ACL,
identity, no-reparse, immutable atomic/hash controls. No OneDrive/Git fallback.

Remaining before retrieval: explicit approval of this request/credential behaviour/
storage/budget; resolution of current endpoint support, applicable account
entitlement and limited-use/retention permission; separately reviewed admission
for the exact source revision/spec/native identity and one durable session.
Retain ENDPOINT_SUPPORT_NOT_RUNTIME_VERIFIED and USAGE_PERMISSION_NOT_FULLY_ESTABLISHED.
No account-specific route substitution, support contact or bulk authorisation.

**No authenticated request is authorised by V2.7 implementation. Production trading remains NO-GO.**
