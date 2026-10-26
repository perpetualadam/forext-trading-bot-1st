# STAGE D.26 — OFFLINE DUAL-ARCHITECTURE DEPENDENCY METADATA ACQUISITION PLANNING REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D26_OFFLINE_METADATA_PLANNING_COMPLETE`
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
- Production source modified: no
- Network requests: 0
- Metadata downloads: none
- Dependency resolution: none
- Recommended next action: seek a separate approval for the written D.26-R1 discovery bounds. That stage was not started.

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
- Working-tree status: dirty before D.26. HEAD does not identify the working-tree bytes.
- Protected hashes: the ten expected digests match the current files and the D.21 baseline.
- Earlier evidence integrity: D.22 through D.25 classifications remain in place.
- Unexpected changes: none caused by this stage.

## 4. OCI EVIDENCE INTEGRITY

- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes
- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes
- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes
- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes
- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes
- Parent-child descriptor checks: the index descriptors, manifest config descriptors, and raw config hashes agree.
- OCI validation verdict: both configs are linux objects. AMD64 has no variant. ARM64 variant is v8.

## 5. D.25 RECONCILIATION

- Production requirement count: 9 transcribed lines, matching the D.25 inventory count.
- Exact pins: 0
- Hash pins: 0
- Transitive lock: absent
- Platform-specific locks: absent
- Wheelhouse: absent
- D.25 readiness totals: {"BLOCKED": 4, "DECLARED_IN_LOCAL_SOURCE": 4, "MISSING": 34, "UNVERIFIED": 4, "VERIFIED_CONFIG_DECLARATION": 6, "VERIFIED_LOCAL_BYTES": 12}
- D.25 Option C recommendation: present in `21_next_stage_decision_record.md` and left unchanged.
- Reconciliation verdict: the stored D.25 counts were re-added from the two matrix files. Their runtime claims stay historical.

## 6. DIRECT DEPENDENCY INVENTORY

- Production requirement names: python-dotenv, pandas, numpy, requests, psycopg2-binary, fastapi, uvicorn, oandapyV20, tzdata
- Version constraints: each transcribed production line has a single `>=` specifier.
- Extras: `uvicorn` transcribes the extra `standard`. The other eight lines transcribe no extras.
- Markers: no semicolon appears in the nine production lines. That observation is not PEP 508 validation.
- Native candidates: numpy, pandas, psycopg2-binary, and uvicorn[standard] are present as requirement text. Native code was not established.
- Transitive closure: missing for every direct requirement.
- Development-only requirements: `packaging` and `pytest`, plus an include of `requirements.txt`.
- Parsing limitations: names and specifiers are transcriptions. PEP 508 validity was not established, and the packaging library was not imported.

## 7. TARGET COMPATIBILITY UNCERTAINTY

- AMD64 Python declaration: 3.12.15
- ARM64 Python declaration: 3.12.15
- Measured Python versions: missing on both platforms.
- ABI/SOABI evidence: missing on both platforms.
- libc evidence: family unverified and version missing on both platforms.
- AMD64 wheel-tag evidence: missing. Candidate tags in the plan are not compatibility claims.
- ARM64 wheel-tag evidence: missing. Candidate tags in the plan are not compatibility claims.
- VPS compatibility evidence: missing.

## 8. FUTURE METADATA SOURCE PLAN

- Proposed metadata host: `pypi.org`
- Proposed file host: `files.pythonhosted.org`, excluded from the proposed discovery allowlist.
- Endpoint patterns: `/pypi/{segment}/json` only. Version JSON and the simple index are recorded as out of scope.
- HTTP methods: GET
- Authentication: none. A challenge stops the future stage.
- Redirect policy: do not follow. A redirect stops the future stage.
- Metadata fields: project name, current version, Requires-Python, Requires-Dist, filenames, file type, size, SHA-256, and yanked status.
- Unapproved destinations: every host other than `pypi.org`, including the file host.

## 9. FUTURE NETWORK BUDGET

- Proposed total request count: 9 GET requests.
- Proposed per-project limit: 1 GET request.
- Proposed response-size cap: 16 MiB per response.
- Proposed timeout: 30 seconds per request.
- Proposed total duration: 270 seconds.
- Proposed transfer cap: 144 MiB.
- Proposed maximum projects: 9 direct production names.
- Stop-on-exhaustion policy: stop before request 10. Do not retry, do not add a project, and do not raise the caps inside the run.

## 10. METADATA AND PROVENANCE POLICY

- Schema validation: JSON object shape and SHA-256 hex format can be checked with the standard library. Requires-Python, Requires-Dist, and wheel-tag grammar stay deferred.
- Project identity: compare the returned name with the approved transcribed name without treating that comparison as publisher authentication.
- Release identity: a listed version is an index record, not a selected install version.
- Requires-Python: store the raw declaration. Do not evaluate it in D.26.
- Requires-Dist: store raw declarations for direct projects. Do not resolve them.
- Wheel filename tags: store filenames. Do not treat a tag string as compatibility.
- Published artifact hashes: store SHA-256 fields. Do not download the artifacts.
- Yanked status: store the boolean and whether a reason field exists.
- Publisher authenticity: not established by transport success or an index hash.
- Remaining limitations: ABI, libc, resolution, installation, runtime, signatures, and VPS identity.

## 11. FINDINGS

- D26-DIRECT-01. Evidence: requirements.txt lines 1-9. Evidence level: DECLARED_IN_LOCAL_SOURCE. Impact: The nine transcribed production lines use lower-bound specifiers and contain no hash pins. Required action: An approved metadata stage can list releases, but it still would not select or lock them. Required approval: yes. Production impact: UNVERIFIED.
- D26-TRANSITIVE-01. Evidence: requirements.txt and the absence of a lock. Evidence level: MISSING. Impact: No approved local file establishes a transitive closure. Required action: Release metadata may later quote Requires-Dist. That quotation is not a resolved graph. Required approval: yes. Production impact: UNVERIFIED.
- D26-ABI-01. Evidence: rehashed config bytes. Evidence level: MISSING. Impact: PYTHON_VERSION=3.12.15 is declared. SOABI and ABI tags were not measured. Required action: Interpreter inspection remains a separate stage. Required approval: yes. Production impact: UNVERIFIED.
- D26-LIBC-01. Evidence: verified manifests and configs, with no layer bytes. Evidence level: UNVERIFIED. Impact: No libc family or version was measured. bookworm-slim is a manifest annotation. Required action: Filesystem inspection remains separate from package metadata. Required approval: yes. Production impact: UNVERIFIED.
- D26-WHEEL-01. Evidence: requirements.txt and absent wheel records. Evidence level: MISSING. Impact: No platform-specific wheel filename, tag, or hash is verified for either architecture. Required action: Metadata discovery can record filenames later. A filename is not compatibility. Required approval: yes. Production impact: UNVERIFIED.
- D26-META-01. Evidence: this planning record. Evidence level: PROPOSED_FOR_FUTURE_VERIFICATION. Impact: pypi.org is a proposed metadata host. It was not contacted. Required action: D.26-R1 needs its own approval and must stay inside the written budget. Required approval: yes. Production impact: UNVERIFIED.
- D26-PROV-01. Evidence: no signature or attestation material in the local dependency files. Evidence level: MISSING. Impact: A future index hash would identify published bytes. It would not identify the publisher. Required action: Signature, attestation, or trusted-publisher checks need separate approval. Required approval: yes. Production impact: UNVERIFIED.
- D26-PLATFORM-01. Evidence: separate AMD64 and ARM64 OCI identities. Evidence level: VERIFIED_LOCAL_BYTES. Impact: The two platforms have distinct manifests, configs, and variants. Required action: Wheel evidence must stay split by platform. Required approval: yes. Production impact: UNVERIFIED.
- D26-SAFETY-01. Evidence: historical authorisation boundary. Evidence level: HISTORICAL_OBSERVATION. Impact: Dependency planning does not read production safety state or authorise trading. Required action: Production safety remains a separate, currently unauthorised assessment. Required approval: yes. Production impact: UNVERIFIED.

## 12. FUTURE APPROVAL SPECIFICATION

- Proposed next stage: D.26-R1 controlled read-only direct dependency metadata discovery.
- Exact hosts: `pypi.org` only.
- Exact endpoints: one GET of `/pypi/{segment}/json` for each approved segment.
- Exact package list: python-dotenv, pandas, numpy, requests, psycopg2-binary, fastapi, uvicorn, oandapyV20, tzdata.
- Request limits: 9 total, 1 per project, 30 seconds, 16 MiB, 144 MiB, 270 seconds.
- Allowed response data: the minimised field list in the D.26 plan. File URLs are dropped.
- Prohibited operations: file-host requests, redirects, retries, resolution, downloads, installation, Docker, and production access.
- Stop conditions: unapproved host, redirect, oversize body, malformed JSON, budget exhaustion, or any download.
- Required explicit approval: a later approval that names this closed scope. D.26 does not grant it.

## 13. VALIDATION

- Commands executed: git rev-parse HEAD, git branch --show-current, git status --short for the protected paths, and Python standard-library hashing and JSON parsing.
- Network requests: 0
- Files created: D.26 artifacts under `data/research/adaptive_ensemble/d26/`.
- Files modified: none outside that new directory.
- OCI digest checks: five preserved objects rehashed and matched.
- Protected source hash checks: ten files matched before and after writing.
- Static checks: requirement transcription, D.25 count reconciliation, and OCI schema checks.
- Prohibited operations: none observed.

## 14. FINAL CLASSIFICATION

`D26_OFFLINE_METADATA_PLANNING_COMPLETE`

## 15. NEXT ACTION

D.26 planning completed. No package metadata was fetched. No dependency was resolved. No wheel was downloaded. Python ABI was not measured. libc was not measured. No image was built. Docker was not executed. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
