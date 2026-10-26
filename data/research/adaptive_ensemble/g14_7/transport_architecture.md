# G.14.7 transport architecture

The acquisition workflow lives in `tests/g14_7_transport.py`. It is research tooling. It is not a production client.

## Default

`DEFAULT_TRANSPORT` is `NETWORK_DISABLED`. `NETWORK_ENABLED` is `False`. `AcquisitionWorkflow` accepts a transport in its constructor. `None` fails closed with `missing_transport` before any policy or filesystem work. Any object whose type is not exactly `ScriptedTransport` fails closed with `real_network_fallback` before `exchange` is called.

There is no HTTPS sender class. The workflow does not import `socket`, `urllib`, `requests`, `httpx`, `pip`, or `subprocess`. It does not construct a fallback client when the scripted transport is absent or rejected.

## Synthetic transport

`ScriptedTransport.exchange` returns the next `SyntheticResponse` from a list supplied by the test. It records the `SyntheticRequest` and performs no name resolution and no connection. An empty script fails with `missing_artifact`.

A response carries a status, chunks, a content length, a content type, an optional location, a completion flag, an elapsed-millisecond field, and a header size. Elapsed time is a number the workflow compares with `TIMEOUT_MS` (5000). The workflow does not sleep and does not arm an operating-system timer.

## What the workflow calls

Before any artifact exchange the workflow calls the existing G.14.6 functions:

- `authorize_url` for the proposed index URL
- `reject_additional_indexes`
- `build_acquisition_environment` with an empty inherited mapping unless the caller supplies one
- `parse_requirement_document`
- `evaluate_marker` when a requirement has a marker
- `reject_member_name`, `assess_wheel_candidate`, and `reject_case_colliding_names`
- `assert_destination_boundary` on the parent and on the child path

After the destination handle exists, every index and artifact hop calls `authorize_redirect_chain` on the URLs seen so far, then asks the scripted transport for one response. The transport does not follow redirects. The workflow authorizes the next location before the next exchange.

Received wheel bytes are written and read back through `tests/g14_7_fs.py`. `verify_member_bytes` checks those bytes. The lock file is written only after that verification returns.

## Limits

| Control | Value |
| --- | --- |
| Maximum artifact | 1048576 bytes |
| Maximum cumulative artifacts | 4194304 bytes |
| Maximum header block | 8192 bytes |
| Maximum chunk | 65536 bytes |
| Retryable statuses | 503 |
| Retries | 2 additional failures, then `retry_exhausted` on the next retryable status |
| Redirect statuses | 301, 302, 303, 307, 308 |
| Redirects | `MAX_REDIRECTS` from `tests/g14_4_acquire.py` (2) |
| Timeout field | 5000 ms |

## Gaps

Live socket behavior, DNS, certificate checks, proxy behavior, and clock-based timeouts are not implemented and were not exercised. A future sender would have to satisfy this same request, redirect, size, retry, and timeout contract. This stage does not supply that sender.
