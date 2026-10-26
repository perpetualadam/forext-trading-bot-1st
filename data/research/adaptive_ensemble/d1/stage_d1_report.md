# STAGE D.1 — PRODUCTION CHANGE INVENTORY AND DEPLOYMENT READINESS REPORT

Classification: `D1_AUDIT_COMPLETE_DEPLOYMENT_BLOCKED`

## 1. EXECUTIVE SUMMARY

- Overall assessment: the audit is complete enough to block deployment. The local tree is not what a restart would run, and it is not safe to build or start.
- Main changes identified: no uncommitted change under `forex_bot`. The Dockerfile is the explicit allowlist COPY and is the only allowlist file that differs from G.10. A G.12 sample of the historical image differs in five runtime files and lacks `market_provenance.py`. Research from G.13 through G.14.12 is untracked and is not a deployment.
- Main deployment blockers: current container not re-inspected, startup calls OANDA and rewrites safety state, safety schema can be destroyed, dependencies unlocked, no candidate image, no verified rollback.
- Whether a restart would apply new code: NO.
- Whether a rebuild is required: YES, before current source can run in a container. A rebuild is not authorised.
- Recommended next stage: an approved offline change to the safety-state writer, with synthetic tests. Not a restart, not a build, not D.2 automatically.

## 2. LIVE SAFETY

- Production container changed: no action taken. Current state was not inspected.
- Docker commands: 0
- WSL commands: 0
- VM commands: 0
- Broker requests: 0
- Broker mutations: 0
- Production database access: 0
- Operational-state access: 0
- Shadow-mount access: 0
- Network requests: 0
- Dependency downloads: 0
- Package installations: 0
- Live-order authorisation: historically BLOCKED (`operator_preflight_blocked`). Not read and not written.
- Active strategies: historically the six remain inactive. The durable file was not read. Source can restore `active` from that file on startup.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec` (2026-10-10 10:56 +0100)
- Branch: `main`
- Working-tree changes: 44 porcelain entries. Six tracked modifications. No staged, deleted, or renamed files.
- Dockerfile integrity: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- .dockerignore integrity: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`
- Frozen evidence integrity: G.10 allowlist, archive, and canonical manifest match. G.7 archive and canonical manifest match.
- Unexpected changes: none. The porcelain count is 44 rather than the G.14.12 figure of 43 because `g14_12/` is now untracked.

## 4. CHANGE INVENTORY

- Production runtime changes: no uncommitted `forex_bot` diff. Versus the G.12 image sample, `bot_loop.py`, `oanda_client.py`, `oanda_exec.py`, `live_manage.py`, and `decision_skip_log.py` differ. `market_provenance.py` was absent from the image. `app.py`, `live_safety.py`, `database.py`, and `main.py` matched the sample.
- Strategy changes: no uncommitted diff. Image bytes of `strategy_meta.py` were not compared.
- Risk-management changes: `live_manage.py` differs from the image sample.
- Safety changes: `live_safety.py` is unchanged since G.7 and matches the image sample. The forward-compat defect is still there.
- Startup changes: `app.py` matches the image sample.
- Database changes: `database.py` matches the image sample. Live schema is unknown.
- Packaging changes: Dockerfile only. Historical image was built with `COPY forex_bot ./forex_bot`.
- Dependency changes: `requirements.txt` unchanged and unpinned.
- Research-only changes: untracked G.13 through G.14.12 reports, plus modified macro scheduler files that were not opened.
- Test changes: three tracked tests modified; 23 helper and test files untracked.
- Unknown deployed differences: 51 allowlisted Python modules were not in the 10-file image sample. The image had 229 application files in that historical count. Full comparison is `NOT_PROVABLE_FROM_AVAILABLE_OFFLINE_EVIDENCE`.

## 5. FEATURE INTEGRATION

- Features present in source: the six strategies, the live-order gate, startup, additive DDL, v2_shadow imports, and the repaired allowlist.
- Features covered by tests: historical unit and packaging tests exist. They were not run.
- Features included in staging: the 63-file context, re-hashed today, matches the working tree.
- Features known in historical image: the four matching sample files, the five differing files, and the broad COPY instruction. Allowlist packaging is not in that image.
- Features not verified in production: all of them. Staging is not deployment.
- Integration concerns: strategy objects start active; startup rewrites safety state; `run_bot` and the broker modules in the image are not this tree; research packages are excluded from the new COPY and may still be inside the old image.

## 6. TEST EVIDENCE

- Historical test results: G.13.1 recorded 274 passed after an earlier G.13 run of 239 passed and 3 failed. G.14.6 recorded 140. G.14.7 recorded 201 with 2 skipped. G.14.8 recorded 225 with 3 skipped. The stage brief also cites an earlier 1,227, which was not re-located in the JSON opened here.
- Current test status: `CURRENT_TEST_STATUS_UNVERIFIED`
- Unit coverage: files exist for safety, repair, provenance, and v2_shadow.
- Integration coverage: no executed lifespan, broker, or live-database test.
- Packaging coverage: historical scoped tests only. No image build.
- Missing tests: unknown nested safety keys, unknown schema preservation, mocked startup, disposable DDL, rollback drill.

## 7. STARTUP AND RESTART RISKS

- Startup entrypoint: `uvicorn forex_bot.app:app --host 0.0.0.0 --port 8000`
- Lifespan side effects: safety rewrite, PostgreSQL DDL, order and reconcile load, broker client, AccountSummary GET, reconciliation reads, then background loops.
- Scheduler behavior: `run_bot` loops, fetches the account and prices, and cycles symbols. That function's file differs from the image sample.
- Database writes: DDL commit on connect, plus reconcile persistence.
- Operational-state writes: safety JSON under the `data/ops` mount, and operational events.
- Broker interaction possibilities: AccountSummary, position fetch, pending-order fetch, and later cycle calls. Reconciliation's own comment says it does not send orders. The trading cycle can reach order code if gates allow it.
- Safety-state handling: effective auth becomes BLOCKED. Valid strategy flags are restored. Invalid or newer documents are replaced.
- Restart safety classification: `RESTART_SAFETY_UNVERIFIED`

## 8. COMPATIBILITY

- Safety-state forward compatibility: `FORWARD_COMPATIBILITY_DEFECT_CONFIRMED`
- Database compatibility: `DATABASE_COMPATIBILITY_UNVERIFIED`
- Shadow-mount compatibility: unverified. Mount not read. Writer in the image may differ.
- Dependency compatibility: unresolved. Minimum versions are not pins.
- Runtime compatibility: `TARGET_RUNTIME_COMPATIBILITY_PROFILE_INCOMPLETE`

## 9. BUILD READINESS

- Dockerfile state: explicit COPY in the working tree. Not the instruction that built the historical image.
- Build-context state: 63-file staging matches the tree and was not modified. Repository root remains forbidden.
- Dependency lock: none
- Wheelhouse: none
- Base-image digest: unverified
- Candidate image: none
- Build reproducibility: not established
- Remaining build blockers: D1-04, D1-05, D1-06, D1-13, D1-16

## 10. ROLLBACK READINESS

- Historical image: `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`, `ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED`, identity not refreshed
- Verified rollback target: none
- Recovery procedure: not tested. The deleted save archive was not recreated.
- Persistent-state compatibility: a start of this safety code can destroy a newer document. DDL is additive and untested on the live database.
- Rollback classification: NO-GO. Do not use `sha256:a19a2208fcf30f8fa1cf61442cf021dec6d99d809b6907836c834922bfe3e2a5`.

## 11. WEEKEND RESTART ASSESSMENT

- Would restarting apply new code: NO
- Is rebuilding required: YES, and it is not authorised
- Is current source deployable: NO
- Is startup safe: NO for this source. Unverified for the live container.
- Is rollback verified: NO
- Is weekend deployment approved: NO

## 12. BLOCKER REGISTER

- Critical blockers: D1-01 current identity, D1-04 dependency lock, D1-05 reproducible build, D1-07 startup side effects, D1-08 safety forward compatibility, D1-12 broker and safety writes on start, D1-13 no candidate image, D1-14 no rollback target, D1-15 recovery untested
- High blockers: D1-02 incomplete image inventory, D1-03 runtime files differ, D1-06 target profile, D1-09 database, D1-10 shadow mount, D1-11 strategy defaults, D1-16 receiver boundary
- Medium blockers: D1-17 tests not run on this tree
- Low blockers: D1-18 compose fallback database password
- Which blockers can be resolved offline: the safety writer, the strategy default, and a mocked test run. They do not by themselves authorise a build.
- Which require separate approval: Docker, network, downloads, Windows changes, live inspect, database fixtures, and any production start

## 13. SHORTEST SAFE DEPLOYMENT PATH

- First remediation: safety-state writer, on synthetic files, under a separate approval
- Required tests: nested-key and unknown-schema tests, then the existing unit set with the broker mocked
- Required packaging work: lock, approved wheels, isolated context, no repository-root build
- Candidate verification: image manifest against the staged hashes, still with trading blocked
- Rollback preparation: a drill that does not use the unsafe historical image
- Future deployment decision: only after every critical and deployment-blocking high item is closed and a separate approval exists

## 14. VALIDATION

- Commands executed: Git metadata, hashes, allowlist compare, staging re-hash, AST parse. Listed in `validation_log.json`.
- Files read: Dockerfile, requirements, compose structure, allowlist, manifests, selected source, and prior G.12–G.14 research. `.env` and both backup files were not opened.
- Files created: the D.1 research documents
- Files modified: none outside `data/research/adaptive_ensemble/d1/`
- Tests executed: 0
- Prohibited operations: none performed
- Missing evidence: live container, full image manifest, live safety file, live database, shadow mount, environment values, a current test run

## 15. FINAL CLASSIFICATION

`D1_AUDIT_COMPLETE_DEPLOYMENT_BLOCKED`

The baseline is intact. The change inventory against Git, the G.10 allowlist, and the staging context is complete. The inventory against the live image is incomplete and is recorded as such. Deployment blockers remain. That is sufficient for this classification. It is not a partial audit in the sense that the next step is unknown.

## 16. NEXT ACTION

- Stage D.1 is complete.
- All changes are not implemented as a deployable unit. The working tree has the repaired Dockerfile and research evidence. Five runtime files differ from the sampled image.
- All changes are not integrated into the running process.
- All changes are not tested on this tree.
- All changes are not deployed.
- A restart is not recommended.
- A rebuild is required before current source can run, and it is not authorised.
- Deployment is not authorised.
- Live trading is not authorised.
- A separately approved next stage is recommended for the safety-state writer and synthetic tests. Do not start that stage from this report alone.

PRODUCTION DEPLOYMENT: NO-GO.
ROLLBACK: NO-GO.
