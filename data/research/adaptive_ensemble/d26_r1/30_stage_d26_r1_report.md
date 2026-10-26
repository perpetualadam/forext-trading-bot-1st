# STAGE D.26-R1 — CONTROLLED READ-ONLY DIRECT DEPENDENCY METADATA DISCOVERY REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D26_R1_METADATA_DISCOVERY_COMPLETE`
- Gate A: PASS
- Gate B: PASS
- Gate C: PASS
- Gate D: PASS
- Gate E: PASS
- Gate F: PASS
- Gate G: PASS
- Gate H: PASS
- Gate I: PASS
- Gate J: PASS
- Source modified: no
- Network requests: 9
- Projects queried: 9
- Metadata retrieved: nine project documents
- Dependency resolution: none
- Package downloads: none
- Recommended next action: Plan an offline review of the retained filename observations. Do not treat those filenames as compatibility results.

## 2. LIVE SAFETY

- Production container changed: no
- Broker requests: none
- Broker mutations: none
- Production database access: none
- Telegram network requests: none
- Operational-state access: none
- Shadow-mount access: none
- Docker commands: none
- WSL commands: none
- VM commands: none
- Image-layer downloads: none
- Dependency downloads: none
- Package installations: none
- Live-order authorisation: historically BLOCKED. Current production authorisation was not independently verified.
- Strategy activation: none. The six strategies remain historically inactive.

## 3. BASELINE INTEGRITY

- Git HEAD: `d080d897945bc44fa37c02caab504ed707146bec`
- Branch: `main`
- Dirty working-tree status: dirty before D.26-R1. HEAD does not identify the working-tree bytes.
- Protected hashes: the ten expected digests match the current files.
- Earlier evidence integrity: D.22 through D.26 remain unchanged.
- Unexpected changes: none caused by this stage.

## 4. OCI EVIDENCE

- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes
- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes
- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes
- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes
- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes
- Descriptor relationships: parent manifests and config descriptors match the rehashed files.
- OCI integrity verdict: linux/amd64 has no variant. linux/arm64 variant is v8. Both configs declare PYTHON_VERSION=3.12.15.

## 5. DEPENDENCY SCOPE

- Nine approved projects: python-dotenv, pandas, numpy, requests, psycopg2-binary, fastapi, uvicorn, oandapyv20, tzdata
- Requirement constraints: the transcribed production lines and their specifiers are in the allowlist artifact.
- Extras: uvicorn transcribes the extra standard. The extra was not requested as a separate project.
- Allowlist result: the transcribed segments match the fixed nine path segments.
- Excluded dependencies: development requirements and every Requires-Dist name.

## 6. NETWORK REQUEST LEDGER

- Attempt 1: project python-dotenv, host pypi.org, endpoint /pypi/python-dotenv/json, HTTP status 200, response bytes 112447, elapsed seconds 0.228, redirect False, authentication required False, validation PASS, stop condition none.
- Attempt 2: project pandas, host pypi.org, endpoint /pypi/pandas/json, HTTP status 200, response bytes 2244167, elapsed seconds 0.222, redirect False, authentication required False, validation PASS, stop condition none.
- Attempt 3: project numpy, host pypi.org, endpoint /pypi/numpy/json, HTTP status 200, response bytes 3729087, elapsed seconds 0.292, redirect False, authentication required False, validation PASS, stop condition none.
- Attempt 4: project requests, host pypi.org, endpoint /pypi/requests/json, HTTP status 200, response bytes 192973, elapsed seconds 0.12, redirect False, authentication required False, validation PASS, stop condition none.
- Attempt 5: project psycopg2-binary, host pypi.org, endpoint /pypi/psycopg2-binary/json, HTTP status 200, response bytes 1118630, elapsed seconds 0.191, redirect False, authentication required False, validation PASS, stop condition none.
- Attempt 6: project fastapi, host pypi.org, endpoint /pypi/fastapi/json, HTTP status 200, response bytes 527280, elapsed seconds 0.15, redirect False, authentication required False, validation PASS, stop condition none.
- Attempt 7: project uvicorn, host pypi.org, endpoint /pypi/uvicorn/json, HTTP status 200, response bytes 233469, elapsed seconds 0.126, redirect False, authentication required False, validation PASS, stop condition none.
- Attempt 8: project oandapyv20, host pypi.org, endpoint /pypi/oandapyv20/json, HTTP status 200, response bytes 42289, elapsed seconds 0.156, redirect False, authentication required False, validation PASS, stop condition none.
- Attempt 9: project tzdata, host pypi.org, endpoint /pypi/tzdata/json, HTTP status 200, response bytes 59488, elapsed seconds 0.104, redirect False, authentication required False, validation PASS, stop condition none.

## 7. METADATA INVENTORY

- Projects retrieved: 9
- Release counts: python-dotenv 52, pandas 119, numpy 152, requests 163, psycopg2-binary 27, fastapi 323, uvicorn 204, oandapyv20 20, tzdata 38
- Distribution counts: python-dotenv 102, pandas 2509, numpy 4298, requests 244, psycopg2-binary 1195, fastapi 646, uvicorn 299, oandapyv20 22, tzdata 72
- Reported hashes: SHA-256 fields were retained when they were 64 hexadecimal characters. Missing hashes are marked MISSING.
- Requires-Python, from each project info section only, not evaluated and not a selected install version: python-dotenv `>=3.10`; pandas `>=3.11`; numpy `>=3.12`; requests `>=3.10`; psycopg2-binary `>=3.10`; fastapi `>=3.10`; uvicorn `>=3.10`; oandapyV20 empty string; tzdata `>=2`.
- Reported current version labels, not selected for installation: python-dotenv 1.2.4, pandas 3.0.6, numpy 2.5.4, requests 2.34.2, psycopg2-binary 2.9.13, fastapi 0.143.0, uvicorn 0.54.0, oandapyV20 0.7.2, tzdata 2026.5.
- Requires-Dist: retained from each project info section only. Historical release dependencies were not requested.
- Yanked records: 124 distribution records have yanked true. Yank reasons were not stored.
- Missing fields: a missing SHA-256 or Requires-Python value is marked on the record rather than invented.
- Completeness limitations: COMPLETE

## 8. DUAL-ARCHITECTURE EVIDENCE

- AMD64 candidate filenames: 2209 retained distribution records contain linux-oriented x86_64 filename text or none-any filename text.
- ARM64 candidate filenames: 1574 retained distribution records contain linux-oriented aarch64 filename text or none-any filename text.
- Python ABI: missing.
- libc: unverified.
- Platform tag assumptions: filename substrings were observed. They were not parsed as authoritative wheel tags and they were not accepted as compatibility.
- Compatibility verified: no.
- VPS compatibility verified: no.

## 9. FINDINGS

- D26R1-META-01. Evidence: 9 validated project JSON responses. Evidence level: VERIFIED_LOCAL_BYTES. Impact: The approved index returned project metadata for the queried names. That is not an installation plan. Required next evidence: Use the retained inventory only inside its stated limits. Required approval: no. Production impact: UNVERIFIED.
- D26R1-PYTHON-01. Evidence: requires_python fields and the separate OCI declaration PYTHON_VERSION=3.12.15. Evidence level: DECLARED_IN_RETRIEVED_METADATA. Impact: Index Python constraints were not evaluated, and the interpreter was not measured. Required next evidence: A separate interpreter measurement. Required approval: yes. Production impact: UNVERIFIED.
- D26R1-WHEEL-01. Evidence: distribution filenames retained from the JSON responses. Evidence level: PUBLISHED_FILENAME_OBSERVED. Impact: A filename match is not runtime compatibility for linux/amd64 or linux/arm64/v8. Required next evidence: ABI and libc evidence before any compatibility claim. Required approval: yes. Production impact: UNVERIFIED.
- D26R1-ABI-01. Evidence: no SOABI in the retrieved metadata or local OCI config. Evidence level: MISSING. Impact: Wheel ABI tags remain uncompared with a measured interpreter. Required next evidence: Interpreter inspection. Required approval: yes. Production impact: UNVERIFIED.
- D26R1-LIBC-01. Evidence: no libc version in the retrieved metadata. Evidence level: UNVERIFIED. Impact: manylinux and musllinux filename text was not treated as a libc measurement. Required next evidence: Base-image filesystem inspection. Required approval: yes. Production impact: UNVERIFIED.
- D26R1-TRANSITIVE-01. Evidence: info.requires_dist only. Evidence level: MISSING. Impact: Declared direct requirements were not resolved, and historical releases were not queried. Required next evidence: A separately bounded resolution or release-specific metadata stage. Required approval: yes. Production impact: UNVERIFIED.
- D26R1-PROV-01. Evidence: published sha256 fields. Evidence level: DECLARED_IN_RETRIEVED_METADATA. Impact: A published hash does not identify the publisher and the artifact bytes were not downloaded. Required next evidence: A separate artifact or provenance approval. Required approval: yes. Production impact: UNVERIFIED.
- D26R1-SAFETY-01. Evidence: no production endpoints were contacted. Evidence level: HISTORICAL_OBSERVATION. Impact: Metadata discovery does not establish live-trading safety. Required next evidence: A separately authorised production assessment. Required approval: yes. Production impact: UNVERIFIED.

## 10. FUTURE DECISION

- Recommended next stage: Plan an offline review of the retained filename observations. Do not treat those filenames as compatibility results.
- Evidence gap addressed: the retained inventory can support a later offline review of filename observations. It does not measure ABI or libc.
- Required permissions: a new offline stage may read only the D.26-R1 artifacts and local source. Any new network, download, or layer inspection needs its own approval.
- Prohibited activities: package downloads, dependency resolution, installation, Docker, and production access.
- Remaining uncertainty: selected versions, transitive closure, ABI, libc, publisher identity, runtime behaviour, and VPS suitability.

## 11. VALIDATION

- Commands executed: git rev-parse HEAD, git branch --show-current, git status --short for the protected paths, and the standard-library HTTPS client.
- Network attempts: 9
- Response bytes: 8259830
- Files created: D.26-R1 artifacts under data/research/adaptive_ensemble/d26_r1/.
- Files modified: none outside that new directory.
- OCI hashes: five preserved objects matched before the requests and after the report.
- Protected source hashes: ten files matched before and after.
- Prohibited operations: none observed.

## 12. FINAL CLASSIFICATION

`D26_R1_METADATA_DISCOVERY_COMPLETE`

## 13. NEXT ACTION

Metadata discovery completed for all nine projects.
Project request failures: none.
No wheel was downloaded. No dependency was resolved. Python ABI was not measured. libc was not measured. No image was built. Docker was not executed. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
