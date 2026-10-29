# Session rollover with corrected read isolation — local review

Base: 8ecadc8650d0a4abfd521ee2013a24dc69380b6d. The prior 17-file publication approval is superseded. No commit or push is authorised by this correction stage.

The original rollover design is retained: independent identity-bound sessions beneath C:\TradingResearchData\OANDA\sessions\<id>, immutable non-authorising request preparation, session-bound grants/journals/claims/results, source seals and native owner/SYSTEM ACLs. Legacy consumed records stay in place. No migration, reset, alternate archive or downloader was added.

The correction is limited to worker read isolation and directly related tests/review metadata. configure_session_reads replaces its bootstrap set with the exact selected root's eight authority/state filenames. It never unions legacy and namespaced paths. Before validation, no other archive state is readable; after validation ACTIVE_ROOT still confines writes and result reads to the selected session.

Shared reads are explicitly limited to Python's standard-library directory, package-level .py code and its __pycache__ .pyc files, the exact non-authorising source-seal JSON, and the protected archive's identity-binding JSON. Package outputs, arbitrary reports and proposal JSON are not shared resources. The broad PACKAGE read exception is removed.

An explicitly selected legacy namespace retains access to its own records/results but excludes its descendant sessions/ container. Resolved junction/symlink escapes are denied. Multiple-link own-session files are refused so a hardlink cannot expose another session's authority. The existing write/mutation checks use the same own-root boundary.

The global acquisition lock, durable reservation, grant proof, namespace identity, one-attempt restriction and no-retry/redirect/proxy/pagination/fallback rules are unchanged from the previously tested rollover implementation. Startup remains 15 seconds, hidden entry up to 120 seconds, then a fresh 15-second acquisition/cleanup budget. HTTP still requires durable reservation and a valid post-input phase. OS scheduling and uninterruptible kernel I/O are not hard real-time guarantees.

New tests use an isolated test-only child mode in test_v27_rollover.py. The runner permits only that exact script/flag and the existing minimal environment, only in rollover-test mode. The child rejects roots outside synthetic fixture trees and installs the actual worker audit hook before real file operations. No test-only reader or arbitrary path probe is added to the production worker protocol.

The corrected 17-file scope is staged for renewed review only. Operational files, R.56, frozen strategies, unrelated scheduler work, local data and previous UNKNOWN evidence are preserved. No executable LIVE grant, real credential access or OANDA request occurred. Production trading remains NO-GO.
