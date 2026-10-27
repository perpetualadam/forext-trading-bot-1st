# V2.6 Data Acquisition Plan

NOT_EXECUTED. Proposed scope for a later explicit Permission B review:
2023-09-01T00:00Z <= candle start <2025-09-01T00:00Z, six existing FX instruments,
M5 and unsmoothed MBA. Mid is requested from the source so no midpoint extrema
need fabrication. Derive M15/H1/H4 once; D1 disabled. Practice host is proposed,
not confirmed. Live host use would require its own explicit scope approval.

1266 deterministic windows at1000 candle intervals, at most3 attempts
each, >=1 second spacing and2GiB logical-byte budget. Actual market availability,
response sizes, permissions, endpoint support and coverage are unknown. Individual
requests use from=start and to=end-1 second, includeFirst=true, no count. This
assigns each aligned candle to one half-open window without relying on whether
the API's end bound is inclusive. Any returned out-of-range start is refused.

Before any authenticated request: confirm exact route and intended environment,
applicable market-data/API terms, safe credential access, protected storage and
explicit approval of this concrete scope. Current workspace is under OneDrive;
ignored Git status alone does not prevent cloud sync. No authenticated archive
location has been approved. Credentials are neither requested nor inspected now.

Production remains NO-GO.
