# R.87D CI results

**CI FAILED. OFFLINE_COORDINATOR_CI_COVERAGE_MISSING.**

Exact pushed main SHA: 9ba819cf1f08b92780a19df5f1d8e54df2c2134d.

One workflow run was returned for this SHA: CI, push event, run 40415275679, completed/failure. https://github.com/perpetualadam/forext-trading-bot-1st/actions/runs/40415275679

One job: test, completed/failure. https://github.com/perpetualadam/forext-trading-bot-1st/actions/runs/40415275679/job/121895923981

Job steps: setup success; checkout success; setup-python success; install dependencies success; Run tests failure; post setup-python skipped; post checkout success; complete-job success. No pending or cancelled job remains in this run. No local package installation was performed; GitHub ran the repository's pre-existing workflow.

Current run's pytest summary: **300 failed, 2789 passed, 64 skipped, 127 warnings, 144 errors in 62.48 seconds**. The existing parent run 40382545308 at 883752f91510f639d354f090331446dcc6ade0a8 reported **300 failed, 2789 passed, 64 skipped, 127 warnings, 144 errors in 111.93 seconds**. Parent URL: https://github.com/perpetualadam/forext-trading-bot-1st/actions/runs/40382545308

Failure investigation compared decoded job logs obtained through the GitHub connector. All 444 failure/error node identifiers match between parent and child: zero added, zero removed. Representative families include existing source-hash fixtures in D8/D9, startup/lifespan, G14 security/filesystem/integration and decision-path tests. This is evidence of the same observed baseline failure set, not a claim that their root causes have all been repaired or every diagnostic byte is identical. ci_failure_comparison.json records both summaries and every failure/error node, without retaining raw job logs or credential values.

The workflow is .github/workflows/ci.yml. It runs python -m pytest -q with pytest.ini testpaths=tests. It never executes offline_exposure/run_checks.py, and the coordinator tests are outside discovery. The local 10/57/48 results therefore have no corresponding GitHub offline-suite verification. No workflow was added outside commit scope. A request to list workflow definitions through the connector was rejected as unsupported; run listing, job/step inspection and decoded logs succeeded. Actual run results, not the failed listing request, establish the CI status above.

Branch metadata reported protected=false, required-status contexts empty/off, and rulesets empty. No configured required check is advertised; this does not make the failed CI successful. The highest requested classification available is R87D_MAIN_UPDATED_CI_NOT_VERIFIED because main was updated but CI failed and offline coverage is missing. No additional push, rerun, speculative operational correction or assertion weakening followed the failure.
