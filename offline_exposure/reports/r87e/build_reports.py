"""Serialize the R.87E diagnostic evidence; no application imports or network."""
from pathlib import Path
import collections
import csv
import json

P = Path(__file__).resolve().parent
rows = json.loads((P / 'inventory_evidence.json').read_text(encoding='utf-8'))
counts = json.loads((P / 'inventory_counts.json').read_text(encoding='utf-8'))
linux = json.loads((P / 'linux_clean_result.json').read_text(encoding='utf-8'))
before = json.loads((P / 'source_before.json').read_text(encoding='utf-8'))
after = json.loads((P / 'source_after.json').read_text(encoding='utf-8'))
classification = 'R87E_CI_REPAIR_PROPOSAL_PARTIALLY_VERIFIED'
sha = '9ba819cf1f08b92780a19df5f1d8e54df2c2134d'
current_url = 'https://github.com/perpetualadam/forext-trading-bot-1st/actions/runs/40415275679'
parent_url = 'https://github.com/perpetualadam/forext-trading-bot-1st/actions/runs/40382545308'


def write(name, text):
    (P / name).write_text(text.strip() + '\n', encoding='utf-8')


write('R87E_EXECUTIVE_SUMMARY.md', f'''
# R.87E executive summary

**{classification}**. Production remains **NO-GO**. No commit, push, merge, operational edit, marker fabrication or package installation.

The current and parent GitHub runs each report 300 failures, 144 setup errors, 2,789 passes and 64 skips. Fresh log parsing independently matches all 444 failing/error node IDs. Normalized assertion summaries and exception blocks agree for 442; two R21 selector failures report different selected strategies. Equal counts alone were not used to infer identical failures or root causes.

The CSV inventories every node with current/parent diagnostics, stage, evidence, likely cause, classification, confidence, offline-execution status and recommended action. Traceback-supported mechanisms cover 321 outcomes; 123 remain UNKNOWN. All 144 setup errors are explained at their failing boundary: 132 historical hash assertions and 12 D7 missing-import fixture errors. Explaining a blocking guard is not proof that its downstream scenario would pass.

A native, clean, source-only sparse Linux checkout of {sha} passes the unmodified runner: **57 tests, 0 failures, 0 errors, 0 skips**, Python 3.12.3. The Windows working tree also passes 57/0/0/0. The tracked archive, byte pins, line endings and native permissions were verified without copying local state. Four source-only failure mechanisms were reproduced, including one actual pure historical test.

Prepared a separate offline-exposure-contract job; the existing pytest job is unchanged. The proposed job has not run in GitHub and does not make the repository green. The investigation is partial because 123 causal classifications and full reproductions of unsafe application tests remain open.
''')

write('R87E_REPOSITORY_BASELINE.md', f'''
# R.87E repository baseline

Root/cwd: C:/Users/Brian/OneDrive/Desktop/Forext Trading Bot 1st. Branch main; HEAD and local origin/main {sha}. Connected GitHub branch metadata independently confirms main at this SHA. The repository has not advanced beyond the requested baseline.

Initial read-only commands: git rev-parse --show-toplevel; git branch --show-current; git rev-parse HEAD; git status --short; git remote -v; git branch -avv. Origin: https://github.com/perpetualadam/forext-trading-bot-1st.git. No index changes, commit, fetch, push, merge, reset, clean, stash or source-repository history/ref mutation was performed in R.87E.

Starting tracked modifications were only the two scheduler files under data/research/macro/consensus_pit/prospective/scheduler (audit.jsonl, state.json). Their contents were not read or edited. Existing untracked proposal and earlier offline reports were preserved. No CI/test source modifications existed at start. All four offline files are tracked in the requested commit, as is R86_SOURCE_REVIEW.zip.

The only new tracked modification is .github/workflows/ci.yml, appending the offline job. New R.87E reports and diagnostic support files are local/untracked. The staged diff stays empty.

Source baseline: 451 selected tracked Python/workflow/config files hashed before changes; 450 unchanged afterward, workflow alone intentionally changed. Full before/after manifests and R87E_SOURCE_HASHES.txt record raw SHA-256. The known bot_loop wrapper mismatch remains: current 2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d; sealed archive a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81. Neither was changed.
''')

write('R87E_CI_WORKFLOW_AUDIT.md', '''
# R.87E CI workflow audit

The original .github/workflows/ci.yml is the only existing workflow. It runs on push to main and pull requests, ubuntu-latest, Python 3.12, pip install -r requirements-dev.txt, then python -m pytest -q. Its paper/practice environment variables are unchanged; they are configuration, not comprehensive I/O isolation. No workflow has been disabled. The proposed offline job is additional and independent.

pytest.ini restricts collection to tests/. Default test-file naming applies. tests/conftest.py explicitly collect-ignores ten historical stage modules that require their own barriers. No pyproject.toml exists. The offline_exposure directory is outside pytest discovery; its runner never imports this conftest. The GitHub aggregate has 3,297 reported outcomes; quiet logs do not provide every passing/skipped node ID, so this is not a fabricated full collection list. Every failure/error node is inventoried.

Collection imports operational modules through many test modules, before autouse fixtures execute. Global fixtures clear some sizing/live variables and set paper mode, and redirect several paths to tmp_path, but do not install universal pre-import network/DB/filesystem barriers or neutralize dotenv everywhere. Config import can load dotenv. Database connections are lazy but test paths can invoke them; stage subprocess tests rely on fakes. Production journal modules and recovery paths require separate scrutiny. Do not run this entire suite in the user's working environment.

Confirmed dependencies: raw source archives for hash tests; platform-native Win32 handle APIs/cmd for filesystem tests; missing sklearn for three research tests; permit arguments for direct adapter calls. No traceback establishes a missing consumed marker as this run's primary cause. Never fabricate it. The six wrapper-patching tests still have their fetch_ohlcv seam; R.87E does not migrate them. Two other missing patch targets are recorded separately.

Observed shared-state hazards: app imports invalidate clean-sys.modules assertions; conftest teardown calls a helper that sets every strategy active; R24 directly replaces psycopg2.connect/database.get_connection and connection state without scoped restoration. These are verified source hazards, not proof that they explain every selector/recovery failure. Two R21 failure values vary across runs. Paired fresh-process tests are needed to prove order dependencies.

Requirements use lower bounds for pandas/numpy. Both CI logs show pandas 3.1.0, numpy 2.5.4, pytest 8.4.2 and python-dotenv 1.2.4; dependency versions are equal across these two runs. Numeric dtype/unit/copy assumptions are plausible remaining research issues, not all reproduced. Python differences alone are not a demonstrated cause. Offline compatibility is actually tested on Windows 3.13.5 and Ubuntu WSL 3.12.3; hosted traceback paths show Python 3.12.15 on Ubuntu 26.04.1.

Original workflow has no explicit permissions stanza. Effective logged token permissions are Contents read, Metadata read, Packages read. New job narrows to contents: read and disables checkout credential persistence; no custom secrets or write permissions are added. Hosted execution of the new job remains unperformed.
''')

class_lines = '\n'.join(f'- {name}: **{n}**' for name, n in counts['classes'].items())
different = [r for r in rows if not r['normalized_summary_matches']]
differences = '\n'.join(f"- {r['test_node_id']}: current `{r['exception_or_assertion']}`; parent `{r['parent_exception_or_assertion']}`." for r in different)
write('R87E_CI_FAILURE_CLASSIFICATION.md', f'''
# R.87E failure classification

Fresh connector reads of the current and parent job logs were parsed independently; the earlier R.87D comparison file was not used as the inventory source. Each of 444 summary nodes maps uniquely to its detailed traceback section: 300 FAILED/call, 144 ERROR/setup, no collection/teardown errors in this inventory. Current and parent node sets match exactly. Both runs: 2,789 passed, 300 failed, 144 errors, 64 skipped, 127 warnings. Current pytest duration 62.48s; parent 111.93s. These are reported hosted results, not local full-suite reruns.

Primary classifications (mutually exclusive, sum 444):

{class_lines}

Previously-present is a separate CSV field, not a root-cause classification. No failure was labelled historical simply because its node also failed previously. Historical hash classification requires a failing digest comparison in the detailed traceback. UNKNOWN entries retain concrete assertions, source locations and investigation hypotheses rather than invented causes. TEST_ORDER_DEPENDENCY is not assigned without a paired order experiment. No missing marker, PostgreSQL outage or source-seal defect is asserted merely from a suggestive file name.

Comparison: 442/444 normalized summaries and exception-line blocks match. Normalization removes memory addresses, generated UUID/32-hex IDs, timestamps and whitespace; 64-character source hashes are retained. Original current/parent assertions and exception excerpts remain in the CSV. Full raw traceback equality is not claimed.

Two differences:

{differences}

These are existing failing nodes with varying selector outcomes, not new node regressions. Shared activation state, mode flags and random legacy selection are plausible contributing mechanisms; causality remains unverified. There are zero newly observed failing/error nodes, but failures can mask other regressions and the old job does not exercise the offline coordinator at all.

Inventory fields include node/file, assertion/exception, stage, both commits/results, previous presence, comparison booleans, primary and contributing causes, source locations, excerpts, confidence, safe-offline status, recommendation and job URLs. CSV round-trip verifies 444 unique rows, with exactly 300 FAILED and 144 ERROR entries. Current: {current_url}; parent: {parent_url}.
''')

group_text = []
for group, n in counts['groups'].items():
    selected = [r for r in rows if r['root_cause_group'] == group]
    kinds = collections.Counter(r['current_result'] for r in selected)
    first = selected[0]
    group_text.append(f"## {group}: {n}\n\n{dict(kinds)}. Primary classification: {first['classification']}.\n\nMechanism/evidence: {first['likely_root_cause']} {first['evidence']}\n\nRecommended action: {first['correction_recommendation']}. Example: {first['test_node_id']}. Confidence: {first['confidence']}.\n")
write('R87E_ROOT_CAUSE_GROUPS.md', '# R.87E root-cause groups\n\nThese are outcome counts, not independent defect counts or promised recoveries. A guard can block many scenarios; correcting a guard mismatch does not establish downstream behaviour. The UNKNOWN group is an explicitly unresolved investigation queue, not one claimed common cause.\n\n' + '\n'.join(group_text) + '''
## Hypotheses not established

No missing consumed-marker root cause is evidenced in these tracebacks. No production DB outage is inferred from tests using fake drivers. The actual wrapper is present, so removing/migrating it is not a justified fix for the current run. Test-order/random-state effects are candidates, not established per-node root causes. The numerical readonly-array refusal is a fixture mutability failure, not a filesystem permission error. Dataset EOL drift is independently shown by a native Git checkout: blob 3ae3c4d061792353b94b8d2be73684f950362f135d47926d1bc8c11a24791091 versus checkout c6d8fbf4045d175ead12310cf91eb29b5f5649ded9e0fcbe5b48baf949b09e18.
''')

write('R87E_LOCAL_REPRODUCTION.md', '''
# R.87E local reproduction

No unrestricted pytest, main.py, run_bot or application startup was executed. A disposable native Linux sparse checkout was prepared from tracked Git objects. representative_repro.py installs import, network, subprocess/native-loader, write and read-allowlist audit barriers before project source loads. It clears inherited environment and verifies refusal sentinels. Execution is bounded by a 30-second parent timeout.

Four mechanisms reproduced as expected, with exact tracebacks in representative_reproductions.json:

1. Actual test_current_protected_hashes_match_d15_baseline from the pure historical test module: AssertionError at tests/test_d15_historical_compatibility.py:91. It reads source bytes only; no app import. Native checkout app hash is 8d4abc71523794f7d50076f96d5cbefb625a963c01a78d8149e4e411baa244a1, matching hosted evidence and differing from that historical baseline.
2. Extracted, unchanged select_interpreter with Path(r"C:\\synthetic\\python.exe") on Linux: EnvironmentRejected(untrusted_executable) at g14_4_acquire.py:108, the same guard reason as the G14 failures. No executable or package manager was launched.
3. Extracted, unchanged open_directory on Linux: FilesystemRejected(handle_api_unavailable) at g14_7_fs.py:311. Its guard refuses before file/native handle operations.
4. Source fragment corresponding to the old lifespan text search: ValueError(substring not found) for raise StartupSafetyAbort in the actual lifespan function. app.py was parsed, not imported or executed.

The last three are source-guard/fragment reproductions, not runs of their complete historical pytest cases. All four expected refusals matched; there were zero unexpected reproduction outcomes. A positive-control historical-pins-differ test passed. No new marker, journal, permission grant or broker fixture was created. Full numerical, lifecycle, selector, database and management cases were not locally reproduced because their full isolation closures remain unverified.

Commands and exact environments are in R87E_TEST_RESULTS.md. Early harness attempts failed before test execution: empty Git template lacked .git/info; a later separate WSL invocation could not find the earlier /tmp checkout. The harness creates .git/info and performs checkout/runner/reproductions in one invocation now. These are harness setup errors, not newly demonstrated product defects. No assertion or operational source was changed to obtain reproduction success.
''')

write('R87E_OFFLINE_COORDINATOR_CI_DESIGN.md', '''
# R.87E offline coordinator CI design

Add a separate job offline-exposure-contract to existing CI. Use ubuntu-latest, actions/checkout@v4 with persist-credentials:false, actions/setup-python@v5 with Python 3.12, then python -I -S -B offline_exposure/run_checks.py. Timeout five minutes; contents:read permission. No custom secrets, install step, app startup, permit/marker creation, continue-on-error, shell success masking, skip condition or dependency on the failing test job.

The unmodified runner independently loads three files by exact paths, installs audit hooks before project imports, clears environment, and blocks network/subprocess/DB/dotenv/application imports and writes. It needs only stdlib and the tracked R.86 archive plus current bot_loop source for its mismatch-evidence test. Its nonzero exit code directly fails the step. The test job remains enabled with unchanged logical lines; static checks verify the original prefix and both job names.

Historical assertion test_33 is intentionally a mismatch-detection/current-state pin: current bot_loop must be exactly 2f1c36dc025d114685e4424402f6866c66aa6eb37d28717027c502a4f447118d, archive exactly a2310a7f2d2aee4b60c3c471cdd56ed48c72e2ed29232047c404209537e58d81, and they differ. Passing it is NOT operational R.86 seal acceptance. The archive is tracked; ZIP bytes are binary; bot_loop is explicitly LF in .gitattributes. Native clean checkout verifies those exact bytes without altering expectations. Other source files acquire CRLF according to existing attributes; their raw hashes may differ from local LF blobs and are separately recorded.

The job command passed in a clean Ubuntu/Python 3.12.3 checkout. Hosted Ubuntu 26.04.1/Python 3.12.15 and the Actions orchestration itself have not executed this uncommitted job. Review, separately authorised publication and an exact-SHA successful job are still required before claiming GitHub coverage is established.
''')

write('R87E_CLEAN_CHECKOUT_VALIDATION.md', f'''
# R.87E clean-checkout validation

Actual execution, not a proposal: Ubuntu WSL, {linux['python']}, {linux['git']}. Native Linux disposable repository `{linux['checkout']}` points to existing commit {sha}. The helper uses a read-only local Git-object alternate, no remote fetch, no credential config, empty hooks template, exact sparse paths and Git's normal attribute checkout. No source-repository index/ref/history was changed and no commit object was created. The Linux temp fixture is diagnostic only and may not persist across WSL sessions.

All 16 materialized paths are tracked: offline files, pure module, bot_loop, binary R.86 archive, .gitattributes and a small source-only representative set including frozen dataset. No .env, credentials, production journals, permits/markers, unrelated untracked files or replacement historical artifacts are copied. Complete tracked_paths, hashes and permissions are in linux_clean_result.json.

The unmodified offline command returned 0 with 57 tests, 0 failures/errors/skips; unittest duration 0.020s and parent wall duration {linux['wall_seconds']:.6f}s. The checkout was clean before and after tests/reproductions, and every materialized byte hash stayed unchanged. Native permissions are 0644; Python runs scripts directly, so executable bits are unnecessary. Relative paths and archive access work without repo-local or third-party dependencies.

Critical hashes: bot_loop `{linux['source_sha256']['forex_bot/bot_loop.py']}`; R.86 archive `{linux['source_sha256']['data/research/adaptive_ensemble/r86/R86_SOURCE_REVIEW.zip']}`. Git normalized blob hashes and checkout raw hashes are not conflated. The pure/new Python files are CRLF under the repository's existing rules; bot_loop remains LF and the ZIP binary. The dataset's LF Git blob matches its expected frozen pin while its CRLF checkout matches the observed CI mismatch. No manual normalization or expected-hash edit was used.

This verifies a clean sparse checkout of all offline dependency paths, not the entire broad application suite or a hosted Actions run. Sparse materialization deliberately avoids production-state artifacts. See clean_linux_validation.py for reproducibility and R87E_TEST_RESULTS.md for exact bounded commands.
''')

write('R87E_CI_REPAIR_PLAN.md', '''
# R.87E controlled repair plan

Only the separate workflow job is implemented here. No operational repair is justified by this investigation alone. Counts are affected outcomes, not guaranteed fixes. Preserve original safety assertions and historical provenance.

1. Review the 15-line offline CI addition, then obtain separate commit/push authority. Run and inspect its exact-SHA job. Retain the existing failing full suite visibly; do not relabel the repository green.
2. FIX_TEST_ISOLATION: 11 clean-import failures require fresh subprocess boundaries before app imports, not sys.modules deletion inside a contaminated interpreter. The 12 D7 setup errors need explicit isolated orders-module loading/fake installation after barriers, rather than relying on historical app import side effects. Scoped DB/network monkeypatches and true strategy-default restoration are separate candidate test-isolation work; pair fresh-process/order runs before attributing the 123 UNKNOWN outcomes. Do not edit operational strategy defaults.
3. FIX_PLATFORM_COMPATIBILITY: 67 G14 interpreter cases need genuinely platform-correct synthetic paths while retaining trust checks. The 26 native handle/cmd cases need explicit Windows coverage plus Linux refusal contracts. Preserve every original safety scenario with a reviewed platform-to-job coverage map; no blanket skip or continue-on-error. Two dataset digest failures support a narrowly reviewed .gitattributes LF exception for the frozen CSV, preserving its Git blob and expected digest; no dataset rewrite or hash refresh. These changes are proposed only.
4. REPAIR_TEST_FIXTURE: 26 legacy adapter calls omit permit arguments. Supply evidence-bound synthetic permissions only inside a transport/network-isolated harness; keep denial/forgery tests and never mint real permit files or weaken validators. The readonly time array case suggests a writable copy in the synthetic _clock fixture, with the original gap assertion unchanged; reproduce with the declared numerical dependency profile before editing it. Missing sklearn requires an explicitly reviewed research test dependency profile; no local installation or deletion of assertions.
5. DOCUMENT_HISTORICAL_FAILURE: 136 raw source-pin outcomes block old baselines. Preserve the recorded digests. Decide which historical tests should run against their matching archived source and which newly reviewed current-source checks are necessary. Do not repin everything to HEAD or restore obsolete operational behaviour merely to pass. A failed pin is not evidence its intended lifecycle scenario executed.
6. UPDATE_SUPERSEDED_TEST_CONTRACT: follow actual startup/cycle call chains for the 13 source-text assumptions. Preserve before-resource-acquisition safety ordering with semantic assertions. For 21 observation/durable-close expectations, require observation-only discovery and retained unconfirmed exposure rather than managed adoption or deletion from broker-flat alone. The two missing patch targets are diagnostic only; they are in protected wrapper-dependent files and cannot be migrated in this stage.
7. FIX_TEST_ISOLATION for the DNS failure: block sockets/DNS before imports and verify sentinel refusal; never allow the actual resolver call merely to match an exception. No marker was observed as the primary failure; do not fabricate one.
8. DEFER_PENDING_EVIDENCE for 123 unresolved outcomes, particularly numerical/time-unit assumptions under pandas 3.1.0, selector flags/random state, management evidence and fake DB cursor contracts. For any later proposed operational repair, name the exact function and demonstrate the defect with minimal disposable input, define the smallest change and risk, specify regression tests and expected effect. No such operational patch is authorised here.

Separate work remains the sealed wrapper/consumer review. R.87E neither removes/restores the wrapper nor migrates any of its six tests. Do not weaken production gates, quarantine, close evidence, sizing, stops, profit protection or weekend handling. A genuinely green repository requires passing full-suite results after individually reviewed corrections; adding one green offline job is insufficient.
''')

write('R87E_TEST_RESULTS.md', f'''
# R.87E test results

## Actual final executions

- Windows working tree, Python 3.13.5: `python -I -S -B offline_exposure/run_checks.py` — **57 tests, 57 passed, 0 failures, 0 errors, 0 skips**, 0.021s. windows_runner.log.
- Native Linux clean sparse checkout, Python 3.12.3: the same command under a 60-second parent timeout — **57 tests, 57 passed, 0 failures, 0 errors, 0 skips**, 0.020s unittest duration. linux_clean_runner.log; parent wall time {linux['wall_seconds']:.6f}s.
- Four source-only failure reproductions under a 30-second timeout matched expected exception/refusal outcomes; one additional historical-pin positive control passed. These are NOT five claimed pytest passes. representative_reproductions.json contains exact tracebacks and labels the actual test versus extracted fragments.
- CSV round-trip/uniqueness and 300 FAILED + 144 ERROR totals verified. Workflow structural preservation and no bypass/skip/dependency-install checks passed; git diff --check passed. No YAML/actionlint package was installed or run, and no hosted workflow execution was triggered.

## Exact Linux driver command

```powershell
wsl -d Ubuntu --exec /usr/bin/python3 -I -S -B '/mnt/c/Users/Brian/OneDrive/Desktop/Forext Trading Bot 1st/offline_exposure/reports/r87e/clean_linux_validation.py' '/mnt/c/Users/Brian/OneDrive/Desktop/Forext Trading Bot 1st'
```

The driver performs native Git materialization and runs the isolated child command, then representative_repro.py in the same invocation. Direct reproduction against an earlier /tmp path failed because it was unavailable in the next invocation; no unsupported cause for that disappearance is asserted. The driver now owns fixture lifetime. The initial missing .git/info error was fixed in the disposable harness. One first static check incorrectly included the workflow push key as a job; it was corrected to inspect only jobs. An attempted report JSON patch was rejected before mutation and regenerated through the report serializer. These are tool/harness errors, not hidden product test failures. Earlier successful clean runs were 57/0/0/0; final logs above supersede their timing only.

## Hosted evidence, not rerun here

Current CI: 2,789 passed, 300 failed, 144 errors, 64 skipped, 127 warnings, 62.48s. Parent: same counts, 111.93s. All 444 IDs match, 442 normalized summaries/exception blocks match; two selector values differ. No full application pytest execution was attempted locally. No failing assertion, archive or marker was changed. No commit, push, merge, CI rerun or speculative repair.
''')

hash_text = ['R.87E raw SHA-256 source integrity', f'HEAD {sha}',
             'No source bytes manually normalized. Git applies attributes in the disposable Linux checkout.',
             'WINDOWS WORKING TREE: before_sha256 after_sha256 path']
hash_text += [f'{before[name]} {after[name]} {name}' for name in sorted(before)]
hash_text += ['', 'NATIVE LINUX CLEAN CHECKOUT RAW BYTES: sha256 path']
hash_text += [f'{digest} {name}' for name, digest in linux['source_sha256'].items()]
write('R87E_SOURCE_HASHES.txt', '\n'.join(hash_text))

write('R87E_SECURITY_REVIEW.md', '''
# R.87E security and scope review

No operational module, existing test, coordinator, source-hash assertion, .gitattributes, dependency manifest, trading gate, strategy, sizing/SL/TP, profit protection, recovery authority, weekend handling, live permit or consumed marker was changed. The known wrapper is untouched. Only .github/workflows/ci.yml changes among 451 monitored source/config paths; 450 raw hashes match. The new job has no operational imports, custom secrets, dependency install, permission grant or broker-write path. Existing full test job remains intact.

Network use was limited to read-only GitHub metadata/log retrieval through the connector. Tests did not contact OANDA, DNS, PostgreSQL, or production infrastructure. Audit barriers were reviewed and sentinel-tested before project code runs. Source-only reproductions block application imports and state I/O. No .env, API-token values, production SQLite journals or DB state were read. GitHub job logs were reduced to failure evidence and public metadata, not credential stores. Synthetic source test constants are not operator credentials.

Docker availability probing reported a denied default ~/.docker/config.json lookup and an absent daemon; no configuration contents were obtained and Docker was abandoned. WSL enumeration first hit service permissions; approved elevation enabled use of the existing Ubuntu runtime. No environment installation, package installation, upgrade, shell startup profile or external broker request followed. This caveat is recorded rather than falsely claiming no attempted denied lookup occurred.

one_session.permit is absent by metadata. No marker contents were read/hashed or marker written. No source enablement or runtime gate operation occurred. Effective live runtime state was not probed, and production remains NO-GO. Native Linux Git operations occur only in disposable /tmp repositories with a read-only object alternate; source repository HEAD/index/history remain unchanged. The temporary ref points to an existing commit; it creates no commit or publication.

R.87E reports/diagnostic scripts are local and untracked. Unrelated scheduler work and earlier reports remain preserved. Trusted-test audit hooks are not an adversarial OS sandbox. No CI green or trading readiness claim is supported by the isolated suite alone.
''')

write('R87E_REMAINING_RISKS.md', '''
# R.87E remaining risks

123 call-stage failures still have UNKNOWN primary causes. Current/parent presence does not settle causality. Numerical copy/time-unit assumptions, shared strategy flags, deterministic-selector mode, fake DB return contracts and authority/evidence fixtures need bounded paired reproductions. Two selector outcomes vary across runs. No broad operational fix or cleanup is justified by this inventory alone.

The new offline job has run only as its exact command in native Linux WSL, not in GitHub Actions. WSL Python 3.12.3 and hosted Python 3.12.15/Ubuntu 26.04.1 are not identical environments. Runtime success, source self-containment and checkout semantics are demonstrated, but orchestration, checkout/setup actions and branch checks still require actual authorised publication and exact-SHA verification. Job coverage must not be marked established before then.

136 source-pin failures are historical provenance gates; their downstream scenarios are often unexecuted. Changing them blindly could hide genuine regressions. Platform scheduling changes must retain Windows security coverage and Linux refusals, not suppress tests. Optional dependency profiles need explicit review; unbounded lower requirements leave numerical assumptions vulnerable.

The wrapper/archive mismatch is intentionally detected by one offline test and remains an operational baseline blocker. No wrapper restoration or six-test migration belongs here. No missing marker should be fabricated; no marker root cause is established in the observed failure set. Production snapshot freshness, broker ordering, real coordinator/process/durability guarantees, recovery fencing, R.87 recovery and R.88 remain outside scope.
''')

write('R87E_FINAL_DECISION.md', f'''
# R.87E final decision

**{classification}**

Diagnostic inventory and proposed isolated job are reviewable; this is not a green CI or trading decision. All 16 requested deliverables are populated. No commit, push or merge was performed. main remains {sha}. The workflow patch and reports remain local; no existing operational/test source was altered.

Why does GitHub Actions fail? It collects application/historical/platform tests together. Confirmed blocking mechanisms include 136 source-pin mismatches, 95 platform outcomes, 36 obsolete source/authority/patch-target expectations, 27 fixture defects, 23 shared-import/fake-install isolation defects, three missing sklearn outcomes and one DNS-reaching test. The remaining 123 are explicitly unresolved. These counts sum to 444 failure/error outcomes, not 444 independently established operational defects.

Inherited or new? All 444 failing/error nodes existed in the parent. 442 normalized summaries and exception blocks agree; two selector values differ. There are no new observed failure IDs, but the old workflow never exercised the offline patch and existing failures can mask regressions. Do not call all traces identical.

Can 57 offline tests run independently in a clean Linux environment? Yes: actual native Linux sparse checkout of the exact commit, real tracked archive, repository-applied line endings and Python 3.12.3 yielded 57 passed/0 failures/0 errors/0 skips with no untracked-state dependency. The proposed hosted Actions job has not executed.

Can a separate job be added without hiding the full suite? Yes: the prepared offline-exposure-contract job is additive, least-privilege, dependency-free, bounded and directly propagates runner failure. Original test job/triggers/assertions stay unchanged. Diff and structural checks are recorded.

Smallest justified sequence: review the new job and evidence; separately authorise publication and verify that job at its exact SHA; then repair demonstrated isolation/platform/fixture issues one logical patch at a time while preserving historical pin evidence and every safety assertion; reproduce UNKNOWN groups before operational proposals. Do not treat the new job as a substitute for correcting the still-failing full suite.

Why partial? One actual pure historical test and three extracted mechanisms were safely reproduced; the complete application cases and 123 causes remain unverified. A clean Linux command run is not a hosted job conclusion. Source before/after manifests show workflow alone changed; no safety gates, live permits, consumed markers, credentials, production journals, PostgreSQL or broker operations were accessed/modified by the tests. Any denied availability-probe caveats are documented in the security report.

Stop after R.87E. Do not start recovery fencing or R.88. **PRODUCTION TRADING REMAINS NO-GO.**
''')

required = [
 'R87E_EXECUTIVE_SUMMARY.md', 'R87E_REPOSITORY_BASELINE.md', 'R87E_CI_WORKFLOW_AUDIT.md',
 'R87E_CI_FAILURE_INVENTORY.csv', 'R87E_CI_FAILURE_CLASSIFICATION.md', 'R87E_ROOT_CAUSE_GROUPS.md',
 'R87E_LOCAL_REPRODUCTION.md', 'R87E_OFFLINE_COORDINATOR_CI_DESIGN.md',
 'R87E_CLEAN_CHECKOUT_VALIDATION.md', 'R87E_CI_REPAIR_PLAN.md', 'R87E_PROPOSED_DIFF.md',
 'R87E_TEST_RESULTS.md', 'R87E_SOURCE_HASHES.txt', 'R87E_SECURITY_REVIEW.md',
 'R87E_REMAINING_RISKS.md', 'R87E_FINAL_DECISION.md']
assert all((P / n).is_file() and (P / n).stat().st_size > 0 for n in required)
with (P / 'R87E_CI_FAILURE_INVENTORY.csv').open(encoding='utf-8', newline='') as f:
    check = list(csv.DictReader(f))
assert len(check) == 444 and len({r['test_node_id'] for r in check}) == 444
print('All 16 requested deliverables populated; CSV verified at 444 unique rows.')
