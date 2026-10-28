# Non-authorising boundary and one-use worker claim

oneshot_authorisation.py:require_live_reservation always raises
AUTHENTICATED_EXECUTION_DISABLED. It issues/accepts no capability. There is no
grant writer, enable flag, generic approval token, copied/stale approval acceptance
or route by which this prompt becomes execution approval.

approval_requirements returns **review metadata**, marked authorises_execution=false:
LIVE, exact SPEC digest, supplied 40-hex source revision and SHA-256 map, fixed
protected root, one attempt, zero retries/redirects/pagination, fifteen seconds,
native identity and unique-session requirements. Changing that boolean does not
authorise anything; tests prove original, copied and modified metadata all refuse.
The metadata builder does not prove the supplied revision is approved/current.

Future admission must independently verify explicit approval against the current
reviewed committed revision and all critical source hashes, the exact request,
held native archive identity, unique one-use session, scope, expiry and unused
durable state. After immutable claim, a provider receipt must prove that same
reservation and worker/session identity. A stale/copy/ambiguous claim must refuse;
no reset, replacement grant or retry. None of that acceptance is activated here.

Dormant integration adds _live_reservation hooks to the existing run_once/reserve
and worker. A real attempt first hits the refusing gate. Below that gate, the
supervisor opens the exact native Archive, holds identity handles and the existing
lock, claims the grant durably and records REQUEST_RESERVED before any Popen.
It releases the lock but retains identity handles throughout the fenced session.
A preparation-budget failure consumes the grant and starts no worker.

The request worker repeats admission before archive access, obtains the same
archive lock, verifies the claimed grant/identity/reserved state and consumes
REQUEST_RESERVED -> REQUEST_ATTEMPTED before emitting RESERVED. The supervisor
then retrieves the token and delivers the bounded packet. A second worker or
restart cannot claim an already attempted state. HTTP failure/timeout/provider
failure does not restore approval. The existing validator/publication/completion
and process fence are reused; no second journal or handoff ledger is added.
Supervisor reservation-before-Popen and single-use worker claim have explicit
in-memory unit tests. The unchanged synthetic branch still reserves within its
fenced worker, preserving every original fixture assertion.

No real acceptance, source-approval verification or grant issuer is functioning;
activation requires separately reviewed admission code. Real-branch unit tests use
synthetic memory doubles, not a real grant or a real privileged request.

The original synthetic restart/crash/timeout/race tests still run unchanged and
prove no second synthetic request. They cannot prove safety of a future admission implementation that does not exist yet.
