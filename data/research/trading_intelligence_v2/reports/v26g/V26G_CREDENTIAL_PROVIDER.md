# Disabled credential implementation

Source-only audit: forex_bot/config.py:8–10 loads dotenv at import; :51 reads
TRADING_MODE; :60 selects OANDA_ACCESS_TOKEN then OANDA_API_KEY. The operational
client strips the selected value and passes it to the SDK in
forex_bot/oanda_client.py:104–118. These modules were read as source, never imported.

oneshot_credentials.py implements ReservedCredentialProvider. Its first operation
is require_live_reservation, which unconditionally refuses in this stage. Only
below that gate is the fixed two-key os.getenv lookup implemented. No .env reader,
Credential Manager access, generic getter callback or token export command exists.
Ordinary acquire_history and run_reserved_history also refuse before lookup,
archive access, worker creation or network activity. The old V2.6E inactive
interface delegates to this same refusing provider.

The token is treated as opaque header-safe ASCII, conservatively restricted to
10–512 letters/digits/dot/underscore/hyphen. This follows the existing transport's
accepted input shape; it does not claim to have inspected the actual token format.
Missing values, whitespace, CR/LF, controls and oversized values refuse with fixed
error codes and suppressed exception text. Operational storage is unchanged.

Dormant controller hooks deliver the value only after RESERVED, through the
existing <=2048-byte stdin packet. No credential in argv, URL, child environment,
object repr, journal, manifest, report or file. The worker receives a separate
credential packet, validates before use and refuses echoed response data before
publication. No account ID is requested or delivered. No token is retained on the
provider object. Python/OS memory and owner/debugger access are not secure-erasure
guarantees; no such claim is made.

Testing: the actual getter is replaced before its guarded body is tested.
The synthetic IPC test checks REQUEST_RESERVED and grant.claimed.json before
calling that body with a synthetic receipt and synthetic token, then runs the
existing child/TLS/validator/archive path. The child does not accept a real grant
or inherit the test's patched admission gate. All ordinary/adversarial calls keep
the original gate and prove no getter/DNS/socket invocation.
