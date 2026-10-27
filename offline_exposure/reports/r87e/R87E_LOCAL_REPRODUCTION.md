# R.87E local reproduction

No unrestricted pytest, main.py, run_bot or application startup was executed. A disposable native Linux sparse checkout was prepared from tracked Git objects. representative_repro.py installs import, network, subprocess/native-loader, write and read-allowlist audit barriers before project source loads. It clears inherited environment and verifies refusal sentinels. Execution is bounded by a 30-second parent timeout.

Four mechanisms reproduced as expected, with exact tracebacks in representative_reproductions.json:

1. Actual test_current_protected_hashes_match_d15_baseline from the pure historical test module: AssertionError at tests/test_d15_historical_compatibility.py:91. It reads source bytes only; no app import. Native checkout app hash is 8d4abc71523794f7d50076f96d5cbefb625a963c01a78d8149e4e411baa244a1, matching hosted evidence and differing from that historical baseline.
2. Extracted, unchanged select_interpreter with Path(r"C:\synthetic\python.exe") on Linux: EnvironmentRejected(untrusted_executable) at g14_4_acquire.py:108, the same guard reason as the G14 failures. No executable or package manager was launched.
3. Extracted, unchanged open_directory on Linux: FilesystemRejected(handle_api_unavailable) at g14_7_fs.py:311. Its guard refuses before file/native handle operations.
4. Source fragment corresponding to the old lifespan text search: ValueError(substring not found) for raise StartupSafetyAbort in the actual lifespan function. app.py was parsed, not imported or executed.

The last three are source-guard/fragment reproductions, not runs of their complete historical pytest cases. All four expected refusals matched; there were zero unexpected reproduction outcomes. A positive-control historical-pins-differ test passed. No new marker, journal, permission grant or broker fixture was created. Full numerical, lifecycle, selector, database and management cases were not locally reproduced because their full isolation closures remain unverified.

Commands and exact environments are in R87E_TEST_RESULTS.md. Early harness attempts failed before test execution: empty Git template lacked .git/info; a later separate WSL invocation could not find the earlier /tmp checkout. The harness creates .git/info and performs checkout/runner/reproductions in one invocation now. These are harness setup errors, not newly demonstrated product defects. No assertion or operational source was changed to obtain reproduction success.
