# Restricted network implementation — inactive

oneshot_network.py fixes api-fxtrade.oanda.com:443 and uses oneshot.SPEC and
request_guard for the exact non-account EUR_USD/M5/MBA GET and time bounds.
fetch_live, _LiveConnection and LiveSocketPolicy all require the refusing real
reservation gate. No factory, host, account, proxy or endpoint parameter is public.

Dormant connector behaviour:

- Resolve the literal host/443 once with explicit TCP stream hints. Reject empty,
  excessive, malformed, non-global, multicast, wrong-port, mismatched-family or
  IPv6 scoped answers. Validate every answer, choose only the first, no fallback.
- Create one raw socket, connect directly to the selected public IP and use
  api-fxtrade.oanda.com for TLS SNI and hostname checking. ssl.create_default_context
  retains trusted roots, CERT_REQUIRED and check_hostname. No fixture CA can enter
  this branch, no proxy environment is copied, and tunnels/reconnection refuse.
- The worker's dormant LiveSocketPolicy admits one exact DNS event and one connect
  to the selected tuple. Other DNS names, destinations, families and second
  connections refuse. Python audit hooks constrain this reviewed process; they
  are not an OS sandbox against malicious owner code or monkeypatching.
- Reuse CandleTransport(attempts=1) and _exchange_get; do not add a downloader.
  No retry, redirect, fallback, pagination, account/order/trade/position route or
  background worker is enabled. TLS/HTTP bodies retain existing bounds/validation.
- Use remaining monotonic budget for connection/TLS/body waits. DNS is bounded by
  the parent worker fence, not by assuming getaddrinfo obeys a socket timeout.
  The controller reserves cleanup time within <=15 seconds. OS scheduling and
  uninterruptible operations are not hard-real-time guarantees.

The existing fixture adapter now delegates to this module's shared one-attempt
exchange. Its separate branch requires SyntheticCredentialProvider-compatible
tokens and the exact validated localhost binding, uses only 127.0.0.1, and retains
certificate/hostname refusal cases. It cannot supply an alternate production host.
Current actual worker operations remain synthetic/loopback because real admission
always fails before its live policy or archive scope can be installed.

Evidence: all existing TLS lifecycle assertions run through the shared exchange;
new fake-DNS/socket tests inspect literal resolution arguments, public-address
validation, SNI, CA/hostname settings and single-connect refusal. No real DNS for
the API host, TLS handshake with OANDA or unauthenticated probe occurred. The real
physical connector and future admission remain unverified against a live account.
