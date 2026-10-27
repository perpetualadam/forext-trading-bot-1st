# V2.6 Read Only Transport

CandleTransport validates method, exact hostname, instrument path and all
query parameters BEFORE invoking its sender. Only GET and six fixed instrument
candle paths are allowed. No account ID is accepted. Both official hosts are
fixed; chosen environment must match the host. No arbitrary URL, port override,
userinfo, query token, encoded path, account-specific route or write method.

Real backend is lazy stdlib HTTPS with certificate validation, fixed GET, bounded
body and no redirect-following library. It does not inherit HTTP proxy environment
configuration. Three attempts maximum; >=1s between serial requests;15s socket
timeout and30s loop deadline, subject to OS DNS/connection timing. No claim of
hard real-time DNS cancellation. Redirects fail, including same-host redirects.
429/5xx retries honour a bounded Retry-After; >60s fails rather than retrying early.

No credential loader or authenticated CLI is provided. In-memory token only after
explicit scoped Approval flags, including terms, endpoint support and credential
review. No such approval exists in this session. Token never enters a URL, repr,
progress record, manifest or response archive. Backend errors and non200 bodies
are discarded/redacted. Synthetic sender tests and mocked stdlib HTTP exercise
the transport without contacting OANDA. The injected sender is a trusted test
seam, not a security boundary against malicious Python code.

Production remains NO-GO.
