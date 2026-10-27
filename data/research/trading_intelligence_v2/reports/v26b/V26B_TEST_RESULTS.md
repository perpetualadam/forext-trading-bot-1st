# V2.6B Test Results

New audit-isolated command:
python -I -S -B data/research/trading_intelligence_v2/v26b_run.py --tests
46 synthetic checks passed on Windows and Ubuntu Python3.12: LIVE selection,
method/route/host refusals, redirect refusal, token handling, one-attempt errors,
M5 MBA validation, inclusive/exclusive boundary models, traversal/link refusal,
atomic publication, hashes and external-root gating. No production paths were read.
Unchanged V26 suite:99 passed, zero failures/errors/skips. No assertion or downloader
behaviour was changed to satisfy this task. Native archive ACL/atomic/hash tests
are separate from portable fixtures and recorded explicitly.

Executed machine evidence: test_results.json, storage_verification.json and
verification.json. Public documentation failures (404 and406) are retained in
public_sources.json; they are not hidden as successful source retrievals.
Initial ignored-directory metadata traversal was denied; tracked source inventory
was used for preservation hashes. No credential files were traversed.
Hosted job outcomes will be verified for the exact published test commit; overall
CI must not be called green while the historical full suite remains failing.

No authenticated requests. Production remains NO-GO.
