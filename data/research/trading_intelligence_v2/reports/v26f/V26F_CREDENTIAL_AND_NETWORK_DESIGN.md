# Credential and network design — inactive proposal

No runtime change is made. References below are relative to the repository root.

Existing source: forex_bot/config.py:8–10 loads dotenv at import; :51 selects
TRADING_MODE; :59 reads OANDA_ACCOUNT_ID; :60 selects OANDA_ACCESS_TOKEN then
OANDA_API_KEY. forex_bot/oanda_client.py:104–118 strips that token and gives it to
the general SDK API. Importing these modules would read configuration and is
excluded. No actual values or credential stores were inspected.

The expected credential is an opaque personal access token used as an
Authorization Bearer value, not an account identifier. No exact token length or
pattern is inferred from a documentation example. The [official authentication
guide](https://developer.oanda.com/rest-live-v20/authentication/) warns that the
token grants access to subaccounts; the local GET restriction does not make the
credential itself read-only.

Current boundary: oanda_existing_readonly.py:14 ExistingOandaCredentialProvider
has no fields or loader and always refuses. Its acquire_history delegates to the
disabled oneshot_bridge entry. oneshot.py:63 reserve accepts synthetic grants
only. oneshot_worker.py:29 audit denies DNS and every connection except the exact
validated loopback port. No --live/--force, real grant writer or usable token loader.

Future credential design, requiring separate implementation approval:

- Select one explicit existing token source only after its applicability is
  confirmed. Reuse the source/key contract, never import Config/get_api or copy
  the entire environment. If the source is only .env, stop for a separately
  reviewed exact-key reader; there is no automatic dotenv fallback.
- Keep the existing isolated controller/worker relationship. Only after the
  archive identity is held, the grant is durably claimed and that same worker
  acknowledges reservation may the controller acquire the selected token and
  deliver it through the existing bounded anonymous stdin pipe. Bind authority
  to the exact spec hash, archive identity, session and worker; no public loader
  callable, arbitrary callback, host or endpoint parameter.
- Require nonempty bounded text safe for one header: reject CR/LF, controls and
  surrounding whitespace. Do not log rejected input. Fixed error codes only;
  suppress chained exception bodies. Never include token in argv, inherited
  environment, URL, journal, report, receipt, trace or Git. Keep response-echo
  refusal and no raw error-body logging. Close pipes and fence the worker on all
  outcomes. Python/OS memory cannot promise secure erasure or protection from
  an administrator, debugger, crash dump or deliberately modified program.

Future network change, design only:

1. Preserve oneshot.py:30 request_guard and exact SPEC; add no destination input.
   Reserve once before credential acquisition, DNS or connection. Record attempted
   dispatch conservatively before potentially observable network activity.
2. Permit one bounded resolution of the literal api-fxtrade.oanda.com for TCP 443
   in the disposable worker. Scope the audit allowlist to that exact resolver
   operation; do not permit arbitrary DNS. Validate returned addresses as public
   unicast, select one address once, then permit one connection to it only. Reject
   empty/invalid/private answers. No alternate address, second DNS lookup,
   Happy Eyeballs race, fallback or reconnection after failure.
3. Connect directly to the selected IP without a proxy, tunnel or ambient SDK
   Session. Use system trusted CAs, CERT_REQUIRED and hostname checking, with
   SNI and certificate hostname api-fxtrade.oanda.com, regardless of selected IP.
   No fixture CA or hostname override may enter the real branch. A valid
   certificate remains necessary even if DNS is compromised.
4. Reuse the reviewed transport/_exchange_get response limits and validator,
   fixed GET/path/query and Host header. Disable redirects, pagination, retries,
   polling and reauthorisation. No account/order/trade/position request capability.
5. Use the controller's monotonic total budget <=15 seconds including DNS, TLS,
   headers, body, validation, publication and fencing; each socket wait uses the
   remaining work budget. DNS can block beyond socket timeouts, so the existing
   parent Job Object/process kill deadline must also fence resolution. Reserve
   cleanup time inside the total budget; OS scheduling is not hard real time.
6. Hold the existing cross-process archive lock and identity handles. Consumed,
   interrupted, pending or ambiguous state refuses a restart; no automatic
   recovery or second request. Use only the bound external NTFS archive and its
   current atomic/hash/ACL/reparse checks, never a OneDrive/Git fallback.

This future branch requires synthetic DNS/address/TLS/timeout/duplicate tests
before activation. Today's successful loopback tests do not verify external DNS,
public CA connectivity or a real-provider implementation. The Python audit policy
is a reviewed-process constraint, not an OS sandbox against hostile owner code.
