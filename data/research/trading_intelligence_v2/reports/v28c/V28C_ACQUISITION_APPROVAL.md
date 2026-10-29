# V2.8C approval preparation — NOT authority

Current authorised real attempts: **0**. No executable grant or real preparation file exists. Do not run the following frontend as part of implementation/testing.

Next action: review V28C_SOURCE.diff and V28C_SHA256.json and separately approve the exact publication scope. Do not commit/push automatically. After publication and CI verification, separately review expanded year-scope rights/capacity, prepare a new non-authorising session namespace/proposal bound to the published seal, and obtain explicit approval for the entire catalogue. None of these later stages is authorised by this report.

Proposed future terminal command (refuses until those preparations exist):

```powershell
python -I -S -B "C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st\data\research\trading_intelligence_v2\bounded_history_entry.py"
```

Required rights attestation, verbatim:
`I CONFIRM ACCOUNT ENTITLEMENT AND PRIVATE RESEARCH RETENTION`

Required existing endpoint acknowledgement, verbatim:
`I ACCEPT ONE NON-ACCOUNT ENDPOINT CONNECTIVITY CHECK`

The frontend additionally displays the entire 106-window scope; the inherited endpoint phrase does not itself authorise 106 requests.

Final confirmation template (no real session ID has been prepared):
`CONFIRM 106 HISTORICAL EUR_USD GETS <new-session-id> 2d5f5b38efb65a0cffd5f63ad38a7da62344d653bdba84dad9438cf1eac96bf9 9a8b0960f0beefe7fb7fbd116cfa320bdfe6b18a2414c936b370a8c3c58445f2`

The exact phrase must be regenerated after any source publication change. It binds the full new session ID, catalogue SHA-256, source seal and maximum 106 attempts. LIVE host api-fxtrade.oanda.com; GET /v3/instruments/EUR_USD/candles; M5/MBA, smooth=false, includeFirst=true, count omitted; exact fixed from/to values only. Coverage [2024-09-01T00:00:00Z, 2025-09-01T00:00:00Z). Archive only C:\TradingResearchData\OANDA. No retries/resume or trading. Approval of publication never creates acquisition authority.

Proposed fixed limits: 15/120/15 s startup/token/per-window, 1,800 s whole acquisition, minimum 1 s pacing, 256 MiB, maximum 106 attempts. An ambiguous or failed entry stops everything and stays spent. A new process does not gain permission to repeat the catalogue.

PRODUCTION TRADING REMAINS NO-GO.
