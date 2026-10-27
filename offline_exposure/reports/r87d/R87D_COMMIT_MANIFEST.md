# R.87D commit manifest

Commit A title: test(offline-exposure): harden coordinator generation and revision checks

Explicit candidate paths:
- offline_exposure/fake_coordinator.py
- offline_exposure/test_contract.py
- offline_exposure/run_checks.py
- forex_bot/exposure_view.py

All are new additions relative to main. The fourth is the separately reviewed, hash-verified pure dependency required by the other three, absent from HEAD. No operational caller modifications. This conditional inclusion is necessary to make the committed runner self-contained within the repository.

Exclude all scheduler work, proposal, reports/logs, research artifacts, ZIP exports, .env/credentials, permits/markers and databases. Use explicit git add paths only; inspect the staged diff and exact path allowlist before commit. Commit B (wrapper and compatibility tests) is not included or approved for merge by this offline patch.

Publication status will be recorded in R87D_GITHUB_MAIN_STATUS.md after execution; this manifest does not claim an unexecuted commit.

Executed publication: commit `9ba819cf1f08b92780a19df5f1d8e54df2c2134d` created on main and fast-forward pushed to origin/main. Exact staged object byte hashes and path list are in staged_manifest.json. No other commit or logical change included. Git index empty after commit.
