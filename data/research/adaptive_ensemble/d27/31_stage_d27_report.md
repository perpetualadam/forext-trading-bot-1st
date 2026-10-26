# STAGE D.27 — OFFLINE DUAL-ARCHITECTURE WHEEL FILENAME AND RELEASE EVIDENCE AUDIT REPORT

## 1. EXECUTIVE SUMMARY

- Overall classification: `D27_OFFLINE_WHEEL_EVIDENCE_AUDIT_COMPLETE`
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
- Package downloads: none
- Dependency resolution: none
- Recommended next action: acquire ABI and libc evidence for the preserved base image. Do not treat filename tags as compatibility.

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
- Working-tree status: dirty before D.27. HEAD does not identify the working-tree bytes.
- Protected hashes: the ten expected digests match the current files and the D.21 baseline.
- Earlier evidence integrity: D.22 through D.26-R1 were unchanged.
- Unexpected changes: none caused by this stage.

## 4. OCI EVIDENCE

- Index digest and size: `sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`, 6546 bytes
- AMD64 manifest digest and size: `sha256:2ed6491b93cd49272ee6de2b5a38440c3448360322c089fc23e370722d74179d`, 1752 bytes
- ARM64 manifest digest and size: `sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`, 1754 bytes
- AMD64 config digest and size: `sha256:4f228bc1cbcfc794e4878312cfc241d368eff55a21c08d1e2bb263116c4ef524`, 5684 bytes
- ARM64 config digest and size: `sha256:eb7d16fec874f15b584063275012ac719885a2b87574d124c0da9c156d504629`, 5699 bytes
- Descriptor relationships: the index descriptors and manifest config descriptors match the rehashed files.
- OCI integrity verdict: both configs declare PYTHON_VERSION=3.12.15. ARM64 variant is v8. The interpreter ABI was not measured.

## 5. D.26-R1 METADATA INTEGRITY

- Nine approved projects: present and unchanged.
- Request-ledger reconciliation: 9 entries, each HTTP 200, no redirects, no authentication challenges.
- Total reported response bytes: 8259830, summed from the retained ledger.
- Retained release counts: 1098 release labels.
- Retained distribution counts: 9387 records.
- Retained yanked counts: 124.
- Retained artifact hashes: 9387 valid-format published SHA-256 fields.
- Metadata integrity limitations: the original HTTP bodies were not retained, so those bytes were not rehashed. The historical filename counts 2209 and 1574 match the retained substring classes. They are not the syntactic tag counts from this audit.

## 6. DISTRIBUTION TYPE AUDIT

- Total distribution records: 9387
- Wheel records: 8006
- Source-distribution records: 1120
- Other records: 261, comprising 260 `bdist_wininst` records and 1 `bdist_egg` record.
- Missing-type records: 0
- Type/extension disagreements: 0

## 7. WHEEL FILENAME AUDIT

- Total wheel filenames examined: 8006
- Syntactically parsed: 8002
- Ambiguous: 4. All four are historical numpy Windows filenames with a numeric build component, `numpy-1.13.3-2-cp27-none-win32.whl` and the cp34, cp35, and cp36 variants. No version was selected from them.
- Invalid: 0
- Unsupported: 0. Records that failed the conservative reader are invalid or ambiguous, not sent to another parser.
- Compressed-tag observations: 1842 wheel filenames contain a dot inside a tag component.
- Parsing limitations: tags were read from the right. A filename with two plausible name, version, and build readings was left ambiguous. This is not a claim of PEP 427 conformance.

## 8. PYTHON 3.12 CANDIDATE AUDIT

- Python-tag observations: cp312, py312, and py3 were treated as relevant tag text. Other interpreter tags were excluded when those three were absent.
- ABI-tag observations: cp312 or abi3 can accompany cp312. none or abi3 can accompany py3 or py312.
- Candidate combinations: 1218
- Excluded observations: 6788
- Ambiguous observations: 0
- Unknown observations: 0
- Measured Python ABI: missing.

## 9. DUAL-ARCHITECTURE COMPARISON

- AMD64 candidate observations: 714 wheels combine a Python 3.12 declared-tag candidate with any, manylinux x86_64, musllinux x86_64, or linux_x86_64 text.
- ARM64 candidate observations: 708 wheels combine a Python 3.12 declared-tag candidate with any, manylinux aarch64, musllinux aarch64, or linux_aarch64 text.
- Universal wheel observations: 584 of those Python 3.12 candidates declare platform tag any.
- Native wheel observations: the remaining candidates declare an architecture-specific Linux tag. manylinux and musllinux are counted separately in the matrix files.
- Yanked candidate observations: yanked records stay in the inventory and are counted separately from non-yanked Python 3.12 candidates.
- Per-project differences: pandas, numpy, and psycopg2-binary have different architecture-specific tag counts. Equal universal-wheel counts do not mean the native wheels match.
- Runtime compatibility verified: no.
- VPS compatibility verified: no.

## 10. RELEASE AND HASH AUDIT

- Release records: 1098
- Distribution records: 9387
- Missing release associations: 0 distribution records lack a retained release label. Numpy has 14 release labels with no retained files, and requests has 3. Those labels were not treated as empty dependency lists.
- Duplicate filenames: 0
- Missing hashes: 0
- Malformed hashes: 0
- Valid-format published hashes: 9387
- Missing sizes: 0
- Yanked records: 124
- Missing timestamps: 0

## 11. FINDINGS

- D27-META-01. Evidence: retained D.26-R1 JSON. Evidence classification: VERIFIED_LOCAL_BYTES for the artifact files, RETRIEVED_INDEX_METADATA for their fields. Supported conclusion: the retained ledger, release labels, and distribution records agree internally. Unsupported conclusion: the original HTTP bodies were rehashed. Impact: completeness is limited to retained fields. Required next evidence: none for this reconciliation. Required approval: no. Production impact: UNVERIFIED.
- D27-WHEEL-01. Evidence: packagetype and filename extension. Evidence classification: RETRIEVED_INDEX_METADATA. Supported conclusion: wheel and source-distribution records were separated, and disagreements were counted. Unsupported conclusion: a source distribution is a wheel. Impact: architecture strings in a source filename were not treated as wheel tags. Required next evidence: none for this separation. Required approval: no. Production impact: UNVERIFIED.
- D27-TAG-01. Evidence: conservative right-side filename reading. Evidence classification: SYNTACTICALLY_PARSED_FILENAME. Supported conclusion: unique readings and ambiguous readings were separated. Unsupported conclusion: the reading is PEP 427 certification or proof of wheel contents. Impact: build-tag filenames with two readings were not assigned a version. Required next evidence: a standards parser only if a later approval allows it. Required approval: yes for any parser installation. Production impact: UNVERIFIED.
- D27-PYTHON-01. Evidence: declared tags plus PYTHON_VERSION=3.12.15. Evidence classification: CANDIDATE_BY_DECLARED_TAGS_ONLY and VERIFIED_CONFIG_DECLARATION. Supported conclusion: some filenames declare cp312, py312, or py3 with a paired ABI tag. Unsupported conclusion: the base image has that ABI. Impact: no wheel was accepted as compatible. Required next evidence: interpreter ABI measurement. Required approval: yes. Production impact: UNVERIFIED.
- D27-AMD64-01. Evidence: platform-tag text. Evidence classification: SYNTACTICALLY_PARSED_FILENAME. Supported conclusion: some Python 3.12 tag candidates also declare x86_64 Linux-oriented platform text. Unsupported conclusion: those wheels run on linux/amd64. Impact: manylinux and musllinux remain unmeasured against glibc or musl. Required next evidence: libc measurement. Required approval: yes. Production impact: UNVERIFIED.
- D27-ARM64-01. Evidence: platform-tag text and OCI variant v8. Evidence classification: SYNTACTICALLY_PARSED_FILENAME. Supported conclusion: some filenames declare aarch64 Linux-oriented platform text. Unsupported conclusion: OCI variant v8 makes those wheels compatible. Impact: ARM64 availability is not uniform across projects or versions. Required next evidence: libc measurement and a later version review. Required approval: yes. Production impact: UNVERIFIED.
- D27-YANK-01. Evidence: 124 yanked flags. Evidence classification: RETRIEVED_INDEX_METADATA. Supported conclusion: yanked records remain visible and were not preferred. Unsupported conclusion: the yank reason is known. Impact: no replacement version was selected. Required next evidence: none unless a later stage needs the reason text. Required approval: yes before using any yanked file. Production impact: UNVERIFIED.
- D27-HASH-01. Evidence: retained SHA-256 fields. Evidence classification: RETRIEVED_INDEX_METADATA. Supported conclusion: valid-format published hashes were counted. Unsupported conclusion: artifact bytes or publisher identity were verified. Impact: a published hash is still metadata. Required next evidence: a separate artifact-download approval. Required approval: yes. Production impact: UNVERIFIED.
- D27-TRANSITIVE-01. Evidence: project-level Requires-Dist only. Evidence classification: MISSING. Supported conclusion: historical release dependencies were not in the retained files. Unsupported conclusion: an empty retained field means a release has no dependencies. Impact: no lockfile exists. Required next evidence: release-specific metadata or an approved resolver plan. Required approval: yes. Production impact: UNVERIFIED.
- D27-SAFETY-01. Evidence: no production access. Evidence classification: BLOCKED. Supported conclusion: this audit did not inspect or change production safety state. Unsupported conclusion: the bot is safe to trade. Impact: filename evidence has no live-trading effect. Required next evidence: a separately authorised production assessment. Required approval: yes. Production impact: UNVERIFIED.

## 12. FUTURE DECISION

- Recommended next stage: controlled interpreter ABI and libc evidence for the preserved base-image snapshot.
- Evidence gap addressed: the missing link between a declared wheel tag and the unmeasured runtime.
- Required permissions: a new approval naming the inspection method. No package download and no production access are implied.
- Remaining uncertainty: selected versions, transitive dependencies, artifact bytes, publisher identity, startup, and VPS identity.
- Explicit approval required: yes. D.27 does not grant it.

## 13. VALIDATION

- Commands executed: git HEAD, branch, targeted status, and a standard-library JSON and filename audit.
- Network requests: 0
- Files created: D.27 artifacts under data/research/adaptive_ensemble/d27/.
- Files modified: none outside that new directory.
- OCI hashes: five preserved objects matched.
- Protected source hashes: ten files matched before and after.
- D.26-R1 evidence hashes: the inspected files matched before and after.
- Prohibited operations: none observed.

## 14. FINAL CLASSIFICATION

`D27_OFFLINE_WHEEL_EVIDENCE_AUDIT_COMPLETE`

## 15. NEXT ACTION

D.27 completed. No metadata was fetched. No wheel was downloaded. No dependency was resolved. No package was installed. Python ABI was not measured. libc was not measured. Docker was not executed. Production deployment is not authorised. Live trading is not authorised. Rollback is not authorised.

PRODUCTION DEPLOYMENT: NO-GO.
LIVE TRADING: NOT AUTHORISED.
ROLLBACK: NO-GO.
