# R55 Gate 2 offline report

Overall: PASS for the offline candidate only.

Gate 3 is not accepted. No real HTTPS session was opened. No real credential was read. No order or trade was sent.

## Architecture

Option A is implemented as two fixed GET descriptions: instruments, then pricing with `includeHomeConversions=true`, host `api-fxtrade.oanda.com`, port 443. The account-summary endpoint stays rejected. The CLI is disabled. `run_live` raises `R55G2_LIVE_DISABLED`. `sealed_live_factory` raises `R55G2_LIVE_TRANSPORT_NOT_ACTIVATED` and does not resolve a name.

## Deadlines

Hard deadlines are enforced on the offline phase interface. They are not guaranteed for `getaddrinfo`, a real TLS socket, or a call that ignores its timeout.

The configured 5.0 second cap stopped a 30 second stall at 5.0001 seconds and did not start pricing. A 0.30 second session budget stopped combined pauses at 0.3001 seconds. A slow body stopped at 0.3003 seconds before the prepared chunks were finished. The 15.0 second constant was demonstrated with an injected clock after the first response; pricing did not start. A non-cooperative 0.25 second sleep against a 0.05 second timeout was not preempted. The session stopped afterwards. Process isolation was not added.

## Credentials

Confirmation is required before the synthetic provider runs. Real input is not executable. Reports and exceptions from the redaction tests did not contain the synthetic token or account identifier. Token permission remains `UNKNOWN`.

## Tests

Attempt 1: 69 passed, 10 failed, 7.97 seconds. The failures were a wrong repository-root index and a path serialisation error in the test helper.

Attempt 2: 79 passed, 0 failed, 0 skipped, 7.72 seconds. The network-denial fixture was active. No test was deselected.

## Integrity

Branch `main`. HEAD `d080d897945bc44fa37c02caab504ed707146bec`. The porcelain line count stayed 256 because `data/research/adaptive_ensemble/r55/` was already one untracked directory. This task added files only under `gate2_offline/`. B1, B2, the eight dependency pins, and the B3 design documents matched their expected hashes during attempt 2.

Manifest SHA-256: `074a5bf3de98724bc6c88612fe8915d228bb3c6f138a1296a388e869036ce7e7`

## Still unresolved

Account home currency, stake mapping, GBP pip value, financing, token permission, executable size, and quote freshness are not established. The account-summary route is not authorised. Whether five seconds is enough for the broker, and how a future DNS lookup would be bounded, remain open. Neither question authorises a connection.

## Authorisation

- Gate 2 offline implementation: complete for this candidate.
- Gate 3 authenticated connection: NOT AUTHORISED.
- Real credentials: NOT AUTHORISED.
- Account-summary endpoint: NOT AUTHORISED.
- Practice orders: NOT AUTHORISED.
- Live trading: NOT AUTHORISED.
- Production changes: NOT AUTHORISED.
- Production deployment: NO-GO.
