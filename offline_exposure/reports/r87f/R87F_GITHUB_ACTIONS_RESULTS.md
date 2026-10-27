# R.87F hosted GitHub Actions results

Exact published commit: a8055c6a9f503a27a8f85d019473f67a3698c3c1. Run 40422484155: [completed/failure](https://github.com/perpetualadam/forext-trading-bot-1st/actions/runs/40422484155). Push event, CI workflow. Remote GitHub main was read independently after push and after terminal completion and points to this SHA, matching local HEAD and origin/main. No reliance solely on local tracking refs.

## offline-exposure-contract

Job 121920025364, completed/success. URL: https://github.com/perpetualadam/forext-trading-bot-1st/actions/runs/40422484155/job/121920025364

All seven setup/run/cleanup steps succeeded. The actual command was python -I -S -B offline_exposure/run_checks.py. Hosted logs contain 57 successful test lines, including audit sentinels; Ran 57 tests in 0.069s; RESULT tests=57 failures=0 errors=0 skips=0; OK. The unmasked checkout SHA evidence confirms a8055c6a9f503a27a8f85d019473f67a3698c3c1. The direct run step concluded success, establishing zero shell/runner exit status with no failure masking. The job has no dependency installation, skipped step, custom secret, continue-on-error or application startup step. Selected non-sensitive log evidence is in hosted_offline_evidence.json.

## Existing full test job

Job 121920025040, completed/failure. URL: https://github.com/perpetualadam/forext-trading-bot-1st/actions/runs/40422484155/job/121920025040

Checkout, Python setup and dependency installation succeeded. Run tests failed with **300 failed, 2789 passed, 64 skipped, 127 warnings, 144 errors in 106.80s**. This pytest failure produces a nonzero test-step status. The default post setup-python cleanup step was skipped following failure; post checkout/complete-job succeeded. That cleanup skip is visible and is not a skipped job, hidden test exclusion or added bypass. Both configured jobs actually ran; neither was cancelled or left pending. No deploy or production execution job is configured.

The full job still runs the unchanged python -m pytest -q command. Numerical dependency versions reported numpy 2.5.4, pandas 3.1.0 and pytest 8.4.2, matching R.87E. Test/error summaries are retained in hosted_full_evidence.json. No raw authentication sections or secrets were saved.

Run started 2026-10-26T23:50:36Z and reached its terminal update at 2026-10-26T23:52:59Z, within the stated ten-minute verification bound. Each wait was at most 20 seconds, with status checks and progress reporting between waits. No CI_PENDING or unavailable state remains. This is **not overall CI green**; the successful offline job and failed full job are separate observed conclusions.
