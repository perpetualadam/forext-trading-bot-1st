# STAGE G.12.1 — INDEPENDENT FORENSIC EVIDENCE VERIFICATION AND ARCHIVE CLEANUP REPORT

## 1. LIVE SAFETY

- Running container changed: no
- Docker commands executed: no
- Docker images built: no
- Docker restarts: no
- Broker API requests: no
- Broker orders submitted: no
- Broker orders closed/cancelled: no
- Live-order authorisation changed: no. It remains `BLOCKED` with reason `operator_preflight_blocked`.
- Strategies activated: no. Six strategies are recorded and none are active.
- Production database writes: no
- Consensus Forecast modified: no

## 2. BASELINE INTEGRITY

- Git HEAD: `f6c4f40ae6b7614379347ed45141ecd5a3d33642`
- Dirty working-tree state: 66 porcelain entries. The tree was not cleaned.
- G.7 archive hash: `0ee97accd2d4a8297a053eb26c5138324192ab5b1f700214acf091d0f6487f82`
- G.7 manifest hash: `ba8eb86d887b44dd44314c6a45c776639bf11bb27f0e92ba2ce24978c3206989`
- G.8 `.dockerignore` hash: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`
- G.10 archive hash: `d0317de858a00b194bc44408932ad6508eec411fe0179b0196175a2985b12277`
- G.10 manifest hash: `93c73c21bd6f144e7d656be74128a771c3274025c0e88b8a052ffbc742f417cf`
- Frozen artifacts preserved: yes. The G.10 allowlist still matches its snapshot. The recorded G.3, G.4, and protocol artifacts verified before the archive was read.

## 3. ARCHIVE VERIFICATION

- Archive path: `C:\Users\Brian\AppData\Local\Temp\forex-bot-g12-forensics\image_save.tar`
- Archive exists: yes
- Archive size: `111919104` bytes
- Archive SHA-256: `ba6f8c3659a599bba1a1b322384ae462dc4d43e8de5a73b7f1001ecca606c948`
- Expected image ID: `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`
- Verified image ID: `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`
- Image configuration valid: yes. Config digest `bb08aef307c6f9915789e1d56e3a4276881372b2a6be6358919d6cf6432313a6`.
- Layer count: 9
- Layers verified: 9. Each compressed blob digest and uncompressed diff ID matches the manifest and image configuration, in order.
- Archive integrity classification: passed

## 4. INDEPENDENT FILE VERIFICATION

- Independent verifier: `tests/g12_1_verify.py`. It does not import the Stage G.12 parser or the temporary analyzer.
- Layer reconstruction: the nine layers were applied in manifest order. The merged application tree contains 229 files.
- Whiteout handling: a `.wh.` entry removes that path and its children from the merged tree. No application path was removed.
- Opaque-directory handling: an opaque marker clears the parent before the layer's new files are applied. No application path was hidden.
- Safety-critical files checked: 10
- Hash matches: all 10 independently calculated results match the Stage G.12 image findings.
- Hash mismatches: none against the Stage G.12 image findings.
- Missing files: `forex_bot/market_provenance.py` is absent from the final image, as previously reported.
- Comparison with G.7: `live_safety.py`, `app.py`, `database.py`, and `main.py` match. `bot_loop.py`, `oanda_exec.py`, `oanda_client.py`, `live_manage.py`, and `decision_skip_log.py` do not. `market_provenance.py` is present in the G.7 snapshot and absent from the image.
- Comparison with G.10: the same four files match. The same five files differ. `market_provenance.py` is present in the G.10 snapshot and absent from the image.
- Independence limitations: the reader uses the standard-library tar, gzip, and hash implementations. It was compared with the Stage G.12 report only after the new hashes were calculated. No discrepancy was found.

## 5. SAFETY FINDINGS

- Fail-closed startup: the image `app.py` lifespan calls `initialise_fail_closed`.
- Persisted `ALLOWED`: `initialise_fail_closed` still calls `_set_effective_blocked` with `persisted_allowed_ignored_until_operator_action`. `_set_effective_blocked` assigns `BLOCKED`.
- New-order gate: `_place_market_order_open_sync` calls `assert_new_live_exposure_allowed` before `oanda_orders.OrderCreate`.
- Strategy inactivity: a missing safety file builds six inactive strategy records. A valid saved document copies the stored active flags. Startup does not contain a path that turns all strategies on.
- Market provenance: `MARKET_PROVENANCE_V2_ABSENT`. The module is absent, `bot_loop.py` and `oanda_client.py` do not import it, and `oanda_exec.py` does not call `require_order_quote`.
- Missing-candle management: `evaluate` returns when `raw` is missing or empty before its later `resolve_broker_manage_price` call.
- Candle exception containment: `CANDLE_FAILURE_MANAGEMENT_REPAIR_ABSENT`. `_contain_candle_exception` and `CycleIntegrityError` are absent.
- Protective-close guards: `LATER_PROTECTIVE_CLOSE_GUARD_ABSENT`. The close function still submits `oanda_positions.PositionClose` through `api.request`. Absence of the later direction and size guard does not, by itself, classify every protective close as unsafe.
- Broker mutation endpoints: `oanda_orders.OrderCreate` in `_place_market_order_open_sync` increases exposure and is gated. `oanda_positions.PositionClose` in `_place_market_order_sync` reduces exposure and does not call the new-exposure gate. No `OrderCancel`, `OrderReplace`, or `TradeClose` call is present. Stop-loss and take-profit fields are attached to `MarketOrderRequest`; they are not separate replace calls. Neither function contains an HTTP method literal or a timeout keyword. Both contain an exception handler and a logger call.
- Startup side effects: `initialise_fail_closed` writes the mounted safety JSON. The lifespan then calls `get_connection`, whose first connection executes `CREATE TABLE IF NOT EXISTS` and `ALTER` statements and commits. This is source structure, not a live database observation.

## 6. SECRET REVIEW

- Files and reports inspected: archive member names, image environment names, Stage G.12 reports, the new verifier, and the written G.12.1 reports.
- Credential exposure classification: `NO_SECRET_EXPOSURE_DETECTED_IN_SCANNED_SCOPE`
- Potential concerns: 154 public CA certificate names were seen, including `usr/lib/ssl/cert.pem` and the system trust store. Their contents were not stored. Image configuration environment values were not stored.
- Values disclosed: no
- Additional review needed: no credential assignment was found in the scanned scope. This is not a claim that the image contains no secret anywhere.

## 7. ROLLBACK ASSESSMENT

- Candidate image: `sha256:a905781d872d4a83706c716baa8be6e08c4abef26b2d9f9510a118c2c3039d25`
- Candidate classification: `ROLLBACK_CANDIDATE_PARTIALLY_VERIFIED`
- Verified safeguards: Stage A fail-closed startup, persisted `ALLOWED` ignored at startup, and the new-order gate before `OrderCreate`.
- Missing safeguards: G.7 market provenance and the G.9/G.9.1 candle-failure management repair and later protective-close guard.
- Database compatibility: `LIVE_DATABASE_COMPATIBILITY_UNVERIFIED`. Image `database.py` matches the G.7 and G.10 snapshots, and its source can run DDL on first connection.
- Mounted-state compatibility: startup rewrites the mounted safety JSON as `BLOCKED` while copying stored strategy flags.
- Rollback procedure: `ROLLBACK_PROCEDURE_UNVERIFIED`
- Safe rollback verified: no

## 8. TEST RESULTS

- Exact commands: the command recorded in `data/research/adaptive_ensemble/g12_1/test_results.json`
- Tests passed: 526
- Tests failed: 0
- Tests skipped: 0
- Static-analysis results: the new G.12.1 modules are ruff-clean. Two pre-existing `utcnow` deprecation warnings remain.
- New findings: none that disagree with the Stage G.12 image hashes.
- Untested paths: the running process, the live database, a rollback procedure, and any broker call.

## 9. ARCHIVE CLEANUP

- Archive retained: no. The operator's script deleted it after a fresh identity check.
- Exact deletion target: `C:\Users\Brian\AppData\Local\Temp\forex-bot-g12-forensics\image_save.tar`
- Exact deletion command: the operator's script checked that the path was a regular file of `111919104` bytes with SHA-256 `ba6f8c3659a599bba1a1b322384ae462dc4d43e8de5a73b7f1001ecca606c948`, then ran `Remove-Item -LiteralPath` on that file only.
- SHA-256 rechecked: matched before deletion
- Parent directory retained: yes. `analyze_layers.py` remains.
- Cleanup approved: yes
- Cleanup performed: yes
- Cleanup risks: the tar cannot be restored from this deletion. The project reports remain.

## 10. FILES CHANGED

- Production source: unchanged by this stage
- Dockerfile: unchanged
- `.dockerignore`: unchanged
- Tests: `tests/g12_1_verify.py`, `tests/g12_1_publish.py`, `tests/test_g12_1_verify.py`
- Audit tools: the verifier and publisher above
- Research artifacts: `data/research/adaptive_ensemble/g12_1/`
- Running production: unchanged

## 11. FINAL CLASSIFICATION

`INDEPENDENT_FORENSICS_VERIFIED_CLEANUP_APPROVAL_REQUIRED`

This classification does not authorise deployment or rollback.

## 12. NEXT ACTION

The operator approved deletion. The identity check passed and only the forensic archive was removed. The parent directory and `analyze_layers.py` remain. No deployment or rollback was authorised.
