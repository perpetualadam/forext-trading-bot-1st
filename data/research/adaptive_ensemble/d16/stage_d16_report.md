# STAGE D.16 — DEPLOYMENT PREREQUISITE AND REPRODUCIBLE BUILD READINESS AUDIT REPORT

## 1. EXECUTIVE SUMMARY

- Overall result: `D16_AUDIT_COMPLETE_DEPLOYMENT_PREREQUISITES_MAPPED`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS
- Gate F: PASS
- Gate G: PASS
- Critical blockers: unpinned dependencies, no lock or wheelhouse, mutable base-image tag, no candidate image, no trusted receiver, no verified rollback target, live schema and production state unverified
- Readiness domains verified: 0
- Readiness domains blocked: 20
- Readiness domains unverified: 3
- Readiness domains partial: 7
- Production source modified: no
- Recommended next stage: a separately approved dependency-lock stage. It is not started here.

Gate PASS means the static audit finished. It does not mean a prerequisite is satisfied. Deployment prerequisites are not satisfied.

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: 0
- Broker mutations: 0
- Production database access: no
- Telegram network requests: 0
- Operational-state access: no
- Shadow-mount access: no
- Docker commands: 0
- WSL commands: 0
- VM commands: 0
- Network requests: 0
- Dependency downloads: 0
- Package installations: 0
- Live-order authorisation: historically BLOCKED. Current production authorisation was not inspected.
- Strategy activation: none. Current production activation was not inspected.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Working-tree status: already dirty. Existing changes were preserved.
- app.py hash: `3ff01244ed217e85d211bec819a7ebff9c96fb0412c56e5a768792ab54b31ca1`
- telegram_control.py hash: `d32b560306fe2f86cc7c8ddbb40aa42842f071bd88ea513d77f172a6a0fadf4c`
- database.py hash: `cf978bfa07a3abc48366f628aac6188a75f69e182f9f8a32251ae91609c1023e`
- live_safety.py hash: `11e55dd74f01f18446c3173fb27b2ec32100de9b9a0f2ae3188c8c377b7bdd44`
- strategy_meta.py hash: `492cab735d04a282678823d82db79b8d2b52205aa4e3bfce26220e66a2f73a1d`
- Dependency manifest hashes: `requirements.txt` `45bc21ba5d8f336c0da5092024cee96103f0251d7c7f55e70056a7c55d194b0a`; `requirements-dev.txt` `0562a6853549077197defb3cd8515521b843a041f2a735723ee2903790e3eef5`
- Dockerfile hash: `4a458b4b393930938831896b5157d26109126dee6c5f64cc46a80fbc0c1463ad`
- .dockerignore hash: `5e8bf75905ffe08b364ee39c20cf031b40b9be8ab74dac497a00d1d93d4fd2fd`
- Compose hash: `f0a374774c35b4c63dce23a837572886d1d53331fec388044bc5887367980179`
- Unexpected changes: none during D.16. `Dockerfile` and the five protected sources were already dirty. HEAD does not identify those working-tree bytes.

## 4. EVIDENCE INVENTORY

- Current local source: the five protected hashes match the expected D.15 baseline.
- Historical source evidence: G.7, G.10, and G.14.1 hashes do not describe the current dirty tree.
- Dependency evidence: two requirements files. No lock and no wheels.
- Packaging evidence: Dockerfile, `.dockerignore`, and `docker-compose.yml` were read as text.
- Runtime evidence: image command is specified. User, digest, architecture, and health check are not.
- Trust-boundary evidence: G.14.12 says the receiver is unverified.
- Rollback evidence: historical image ids only. No verified target.
- Missing evidence: lock, wheelhouse, registry digest, candidate image, receiver, live schema, and current production identity.

## 5. DEPENDENCY REPRODUCIBILITY

- Direct dependency pins: missing. Nine production requirements are lower bounds only.
- Transitive dependency lock: missing.
- Offline wheelhouse: missing.
- Artifact hashes: missing.
- Python compatibility: the Dockerfile tag says 3.12. The host audit interpreter is 3.13.5. Those are not the same target.
- Platform compatibility: missing.
- Native dependencies: `numpy`, `pandas`, and `psycopg2-binary` need platform wheels. The required tags are not recorded.
- Reproducible resolution: missing.
- Reproducible installation: missing. The Dockerfile upgrades pip and installs from an index.
- Dependency provenance: missing.

## 6. CONTAINER BUILD INPUTS

- Base-image reference: `python:3.12-slim-bookworm`
- Registry digest: missing
- Dockerfile: 61 explicit copy instructions. All targets exist. None of those paths is a symlink.
- .dockerignore: excludes `.env`, `/data`, tests, and compose. `.env.example` is re-included for upload and is not copied by the Dockerfile.
- Build-context scope: repository root after ignore rules, then an explicit copy list.
- Packaging allowlist: the current Dockerfile list covers the static import closure of `app.py` and `main.py`. The historical G.10 hash list does not match current bytes.
- Secret inclusion risk: `.env` is ignored and was not read. Fallback password literals exist in compose and `config.py`. Their values were not recorded.
- Runtime state inclusion risk: `/data` is ignored for the context. Compose still mounts operational and shadow paths at runtime.
- Source completeness: static imports from the entrypoints resolve inside the copy list.
- Build determinism: blocked by the mutable base tag, unpinned pip, dirty tree, and unverified daemon behaviour.

## 7. SOURCE-TO-ARTIFACT TRACEABILITY

- Source baseline: local hashes verified. Git HEAD is not sufficient.
- Build-context identity: not sealed.
- Dependency identity: missing.
- Base-image identity: tag only.
- Build process identity: Dockerfile text only.
- Candidate manifest: missing. An analysis schema was written and claims no image.
- Candidate image: none.
- Candidate digest: none.
- Trusted receiver: not implemented.
- Deployment authority: not implemented.
- Rollback target: not verified.

## 8. RUNTIME COMPATIBILITY

- Target OS: not specified beyond the Debian tag in the base image name.
- Architecture: missing.
- Python version: tag 3.12, unverified digest. Host tests from D.15 used 3.13.5.
- Entrypoint: `uvicorn forex_bot.app:app` on `0.0.0.0:8000`.
- Runtime user: missing. No `USER` instruction, so the file assumes root.
- Writable paths: not specified.
- Environment variables: names are listed in compose and `config.py`. Production values were not read.
- Required mounts: compose names `./data/ops`, `./data/research/v2_shadow`, and the `pgdata` volume.
- Health checks: present for the database service and the optional Ollama profile. The bot service and the Dockerfile have none.
- Database schema: source DDL is documented. Live schema is unverified.
- Startup dependencies: compose waits for database health. Application startup also initialises safety state and can contact the broker. That path was not executed.
- Shutdown behaviour: D.15 tested the isolated lifespan. Production shutdown was not observed.
- Production compatibility: unverified.

## 9. TRUSTED RECEIVING BOUNDARY

- Builder identity: missing
- Receiver identity: missing
- Receiver permissions: missing
- Independent verifier: missing
- Deployment authority: missing
- Artifact integrity: missing
- Promotion process: missing
- Trust-boundary status: proposed in earlier research, not implemented
- Required future action: a separate receiver stage. No account or directory was created.

## 10. ROLLBACK

- Known-good image: missing
- Image availability: not checked
- Image integrity: not checked
- Configuration compatibility: unverified
- Database compatibility: unverified
- Persistent-state compatibility: unverified
- Rollback authority: missing
- Rollback procedure: described historically, not verified
- Rollback acceptance: missing
- Final rollback classification: `ROLLBACK_NO_GO`

The historical running image is not evidence of a safe rollback target. The historical unsafe image is rejected. Because rollback is NO-GO, deployment is NO-GO.

## 11. PRODUCTION UNKNOWNS

- Current container: unknown
- Current image: unknown
- Current restart policy: unknown. The compose bot service omits `restart`; that is not a production observation.
- Current configuration: unknown
- Current database schema: unknown
- Current broker state: unknown
- Current safety state: unknown. Historical authorisation remains BLOCKED as a historical record only.
- Current operational state: unknown
- Current shadow state: unknown
- Current rollback target: unknown

D.15 isolated tests do not resolve these unknowns.

## 12. READINESS MATRIX

- Total domains: 30
- VERIFIED_READY: 0
- PARTIAL: 7
- BLOCKED: 20
- UNVERIFIED: 3
- NOT_APPLICABLE: 0
- Critical blockers: D16-DEPS-01, D16-DEPS-02, D16-PKG-01, D16-TRUST-01, D16-ROLL-01, D16-DB-01, D16-STATE-01
- Overall deployment readiness: BLOCKED

## 13. BLOCKER DEPENDENCY GRAPH

- Immediately actionable offline work: none that removes a blocker. The static map is the offline work completed here.
- Work requiring network: dependency locking and a registry digest.
- Work requiring Docker: candidate build, image availability, and any later rollback drill.
- Work requiring production inspection: container identity, live schema, operational state, and shadow state.
- Work requiring elevated privileges: a receiver principal.
- Work requiring explicit approval: every later stage.
- Non-actionable dependencies: deployment, restart, and rollback.
- Recommended order: lock, offline artifacts, base-image digest, copy-set hash manifest, runtime profile, receiver, candidate attestation, disposable schema test, production inspection, rollback proof. Deployment stays after all of those.

## 14. FUTURE APPROVAL PLAN

- A. Lock dependencies. Network may be required. No image and no deploy.
- B. Acquire the locked artifacts offline and hash them.
- C. Record the base-image digest without a production pull.
- D. Hash the current copy set without creating a deployment archive.
- E. Complete the runtime profile offline.
- F. Implement a receiver only under a privilege approval.
- G. Build a candidate only after A–F. Docker required. Production mounts prohibited.
- H. Inspect production read-only. No restart and no broker call.
- I. Prove a rollback target. Do not use the historical unsafe image.
- J. Rehearse on nonproduction data.
- K. Controlled deployment. Not authorised and not reachable.

## 15. DEFECT AND BLOCKER REGISTER

- D16-DEPS-01: `requirements.txt` lines 1–9 are lower bounds. No lock or hashes. Production impact UNVERIFIED.
- D16-DEPS-02: Dockerfile lines 13–14 upgrade pip and install without hashes.
- D16-PKG-01: Dockerfile line 2 uses a mutable base tag and no digest.
- D16-TRUST-01: G.14.12 receiver is unimplemented.
- D16-ROLL-01: no verified rollback image. The historical unsafe image is not acceptable.
- D16-DB-01: source DDL is additive and has no schema version. Live schema was not read.
- D16-STATE-01: production container, image, authorisation, and state mounts were not inspected.

D.1 source findings about strategy defaults and safety-state overwrite were later changed in the working tree and retested offline by D.2, D.3, and D.15. Those later results do not prove the running image contains the fixes. No defect was repaired in D.16.

## 16. VALIDATION

- Commands executed: Git HEAD, branch, and targeted status; SHA-256 of the protected and packaging files; a static AST import walk; a symlink check of the 61 copy sources; host `sys.version`.
- Files read: requirements, Dockerfile, `.dockerignore`, compose, selected source lines, and historical D.1, D.15, G.10, and G.14 reports.
- Files created: D.16 research artifacts only.
- Files modified: none outside the new D.16 directory.
- Static checks: hashes, copy-list existence, import closure, and ignore-rule reading.
- Runtime tests: 0
- Docker commands: 0
- Network requests: 0
- Prohibited operations: none
- Missing evidence: listed in sections 4 through 11. A passing static audit does not mean a future build will succeed.

## 17. FINAL CLASSIFICATION

`D16_AUDIT_COMPLETE_DEPLOYMENT_PREREQUISITES_MAPPED`

All seven gates finished. Thirty readiness domains are classified. Dependency, packaging, trust, and rollback blockers are mapped. Production unknowns are documented. No prohibited operation occurred. Production source remained unchanged.

This classification does not mean the prerequisites are satisfied.

## 18. NEXT ACTION

D.16 completed. Deployment prerequisites are not satisfied. Reproducible dependencies are not verified. No candidate image exists. No trusted receiver exists. No rollback target is verified. Production compatibility was not verified. Production source remained unchanged. The bot may not be restarted. An image may not be built. Deployment is not authorised. Live trading is not authorised. A separately approved next stage is required.

PRODUCTION DEPLOYMENT: NO-GO.

LIVE TRADING: NOT AUTHORISED.

ROLLBACK: NO-GO.
