# Bridge implementation

`oneshot_bridge.py` defines a narrow in-memory synthetic provider and a permanently
disabled normal entry. Provider lookup occurs only after the worker's durable
REQUEST_RESERVED handshake. The accepted provider class performs no I/O or
callback discovery. No token is placed in argv, environment, URL or metadata.

`run_https_fixture()` starts the single monotonic clock before preparation and
delegates to the existing supervisor. The fenced disposable worker starts in
preparation mode so archive I/O itself can be deadline-bounded. It claims the
synthetic grant and commits reservation before the parent obtains/releases the
credential and activates acquisition. Process creation therefore precedes local
reservation; credential access and network activity strictly follow it. There
is no second journal, recovery engine or downloader.

`oneshot_https_fixture.py` is a test-only binding: fixed IPv4 loopback destination,
ephemeral fixture port, explicit ephemeral certificate trust, verified hostname
and one transport attempt. There is no host parameter or insecure TLS mode.
The logical request still must match the unchanged LIVE EUR_USD specification.

V2.6 `CandleTransport` retains its public constructor, production host allowlist,
TLS defaults and fixed headers. Its wire exchange was extracted into private
`_exchange_get()` and is shared with the fixture adapter. An advertised oversize
body, streamed oversize body or truncated declared body fails closed. Existing
injected response objects without a framing attribute retain their old protocol;
real stdlib HTTPResponse framing is checked. No historical test was changed.

The worker uses the existing candle validator and `publish_candles()` adapter,
publishing raw/validated hashes and a manifest last, followed by SESSION_CONSUMED.
Fixture provenance is mandatory. Old C in-memory fixtures keep their previous
publication format and continue to pass.

Windows HTTPS children receive only fixed `SystemRoot` bootstrap metadata to
load Winsock; no parent environment variables or credentials are inherited.
The normal disabled entry cannot select this binding or activate live execution.
