# STAGE G.13 — PRODUCTION PACKAGING REPAIR AND OFFLINE ROLLBACK COMPATIBILITY PLANNING REPORT

## 1. Live safety

- Running container changed: no
- Docker commands executed: no
- Docker images built: no
- Docker restarts: no
- Broker API requests: no
- Broker mutations: no
- Live-order authorisation: `BLOCKED` at the stage baseline, reason `operator_preflight_blocked`. This stage did not write the safety-state file.
- Active strategies: none at the stage baseline. The six original strategies were inactive. This stage did not change strategy flags.
- Production database writes: no
- Consensus Forecast modified: no

## 2. Baseline integrity

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Initial dirty-tree status: the two live scheduler files `data/research/macro/consensus_pit/prospective/scheduler/audit.jsonl` and `state.json`. The prompt expected HEAD `f6c4f40ae6b7614379347ed45141ecd5a3d33642`. That expectation was already stale because the operator committed Stages A–G.12.1. The tree was not reset.
- Frozen artifact verification: matched. G.7 archive, G.7 canonical manifest digest, G.8 `.dockerignore`, G.10 archive, G.10 canonical manifest digest, and the pre-edit Dockerfile hash all matched. G.3 raw and normalised data verified. The protocol digest verified. G.4 artifacts were not modified.
- Original Dockerfile SHA-256: `f8d537d84c8ab004c5fc2cbdc5ef58e8141f5ca66a13be6cc5eac38c7c7006a6`
- New Dockerfile SHA-256: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- Unexpected changes: none in the frozen artifacts. The Dockerfile hash change is the approved repair. Test runs briefly rewrote three G.5/G.6 JSON files; those files were restored. The live scheduler files remained dirty and were not edited by this stage.

## 3. Allowlist verification

- Original allowlist source: `data/research/adaptive_ensemble/g10/production_allowlist.json`
- Expected files: 63
- Verified files: 63 paths present. 62 hashes match the G.10 record. `Dockerfile` differs because this stage repaired it.
- Missing files: none
- Unexpected files: none in the allowlist
- Hash mismatches: `Dockerfile` only, and that mismatch is the repair
- Runtime dependency closure: the import closure from `main.py` and `forex_bot.app` is exactly the 60 allowlisted Python modules. No required module is missing. `requirements.txt` stays the existing install input. `Dockerfile` and `.dockerignore` are build policy and are not copied into the image.
- Remaining uncertainties: the Docker daemon's build-context behaviour is unverified. The closure was static. Installed wheel bytes were not rebuilt. `live_safety_preflight.py`, `decision_repair/harness.py`, and `v2_shadow/score_offline.py` are excluded because the startup closure does not import them.

## 4. Dockerfile repair

- Broad COPY removed: yes. `COPY forex_bot ./forex_bot` is gone.
- Explicit allowlist applied: yes. 59 package files are copied one by one, plus `requirements.txt` once and `main.py` once.
- `main.py` copied once: yes, to `./main.py`
- Dependency installation preserved: yes
- Entry point preserved: `uvicorn forex_bot.app:app` on `0.0.0.0:8000`
- Dockerfile diff: `data/research/adaptive_ensemble/g13/dockerfile_diff.patch`
- Static checks passed: yes. The checker is not a Docker build.
- Docker daemon behavior verified: no. Recorded as `DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED`.

## 5. Packaging exclusions

- Credentials excluded: yes
- Research data excluded: yes
- Tests excluded: yes
- Frozen artifacts excluded: yes
- Operational state excluded: yes
- Git metadata excluded: yes
- Remaining risks: the daemon was not asked to apply `.dockerignore`. Base-image contents and installed packages were not inventoried. Research code under `forex_bot/research/` and `forex_bot/shadow/` is not in the copy list. The packaged tree does include `forex_bot/v2_shadow/` because the running application imports it.

## 6. Database compatibility

- Image/G.7/G.10 schema source comparison: `forex_bot/database.py` is byte-identical. SHA-256 `98ed215c0a7e7f21ecf938172a45805a3f1b456c5cf49e8d0a8ea9f0d5cbce72`.
- Current source comparison: the working tree matches that same digest.
- Startup DDL: on first connection the source creates the six tables if they are absent, adds the known nullable columns if they are absent, creates the known indexes if they are absent, and commits once. The source contains no drop or rewrite.
- Backward compatibility: statically inferred from identical source only
- Forward compatibility: statically inferred from identical source only
- Live database inspected: no
- Classification: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`

## 7. Safety-state compatibility

- Fail-closed startup: a missing file starts blocked with `default_deny_no_durable_state`. An unreadable or wrong-schema file is replaced by a blank blocked document and the known strategies are set inactive.
- Persisted `ALLOWED` handling: startup still forces effective authorisation to `BLOCKED` with `persisted_allowed_ignored_until_operator_action`. The stored `ALLOWED` value remains in a valid document.
- Strategy-flag preservation: a valid document keeps the stored `active` flags. Those flags are independent of the effective order gate.
- Unknown-field handling: unknown top-level keys on a valid document are written back. Extra keys inside a known strategy row are dropped when the snapshot is rewritten.
- Atomic write behavior: the writer uses a temporary file and `os.replace`. A persist error blocks effective authorisation.
- Rollback risks: startup rewrites the mounted document. A newer schema this parser rejects would be overwritten with the blank blocked document. That fails closed and destroys the newer document. Close actions are not covered by the new-exposure gate.

## 8. Shadow-mount compatibility

- Readers: the packaged market idempotency reload and the outcome sibling scan
- Writers: observation append, outcome append, and completed-candle append
- File formats: `observations.jsonl`, `outcomes.jsonl`, and `market/{SYMBOL}_M5.jsonl`, with schema strings `v2_shadow_input_v1` and `v2_shadow_market_m5_v1`
- Compatibility risks: a renamed path or a newly required field can make an older reader skip or reject rows. There is no migration step. The running image's shadow bytes were not re-read, and the deleted forensic archive was not recreated.
- Unverified assumptions: live mount contents are unknown. Shadow output is not production order state. Recovery of the mount is `UNRESOLVED_OPERATOR_DECISION`.

## 9. Rollback planning

- Existing candidate: `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`
- Candidate classification: `ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED`
- Verified rollback target available: no
- Rollback runbook created: yes, `data/research/adaptive_ensemble/g13/proposed_rollback_runbook.md`. It was not executed.
- Backup requirements: `UNRESOLVED_OPERATOR_DECISION`
- Broker reconciliation requirements: required before any recovery that follows persistent-state changes. No broker call was made.
- Operator decisions outstanding: maintenance window, backup location, backup verification, recovery objectives, decision authority, incident log, and health-check acceptance
- Rollback authorised: no

The partially verified image is not a safe fallback for a future deployment. It lacks market provenance, the candle-failure management repair, and the later protective-close guard. Startup of either this source or that image can rewrite the mounted safety file and can run additive database DDL. There is no verified rollback procedure.

## 10. Tests

- Exact commands:
  - `python -m ruff check tests/g13_packaging.py tests/test_g13_packaging.py`
  - `python -m mypy tests/g13_packaging.py tests/test_g13_packaging.py`
  - `python -m pytest -q --tb=line` on the Stage A, F, G.5–G.12.1, G.13, and shadow suites listed in `test_results.json`, plus the one historical Dockerfile assertion
- Tests passed: 239, including 16 new G.13 packaging tests
- Tests failed: 3
- Tests skipped: 0 in that run
- Ruff: all checks passed on the new modules
- Mypy: no errors reported on the new modules
- Untested paths: no Docker build, no daemon context, no live database, no live safety-file rewrite, no broker call, and no process start

The three failures are consequences of replacing the broad copy:

- `test_g10_snapshot.py` compares a fresh working-tree manifest with the frozen manifest. The frozen archive itself is unchanged.
- `test_g11_audit.py` reports allowlist drift of exactly `Dockerfile`.
- `test_macro_prospective_recorder_stage2.py` still expects `COPY forex_bot ./forex_bot`.

Those tests were not edited. Production Python was not edited to silence warnings. Two existing deprecation warnings remain in `bot_loop.py` and `session_rules.py`.

## 11. Files changed

- Dockerfile: repaired
- Production Python: unchanged
- `.dockerignore`: unchanged
- Compose: unchanged
- Tests: `tests/g13_packaging.py`, `tests/test_g13_packaging.py`, `tests/g13_publish.py`
- Audit artifacts: `data/research/adaptive_ensemble/g13/`
- Running production: unchanged

## 12. Final classification

`PACKAGING_REPAIRED_OFFLINE_ROLLBACK_PLAN_PENDING_APPROVAL`

This classification does not mean the package is deployment-ready. The repair matches the audited 63-file set, the static packaging checks passed, and the rollback plan records the unresolved blockers. No image build, deployment, or rollback is authorised.

## 13. Next action

The single safest next verification step is a separate, permission-gated offline Docker build-context and candidate-image verification stage. That stage is not authorised by G.13 and was not started. It would need its own approval because it talks to the Docker daemon and exposes the build context. Static tests are not permission to build.

Before that stage is useful as a commit, the three historical tests that still pin the pre-repair Dockerfile need a separate edit. This stage did not make that edit.
