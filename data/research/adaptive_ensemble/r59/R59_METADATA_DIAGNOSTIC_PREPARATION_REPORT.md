# R.59 instrument-metadata diagnostic preparation

**REAL_NETWORK_EXECUTION_NOT_TESTED**

Production trading remains NO-GO. The R.59 source gate is `False`. No permit was created. OANDA was not contacted.

## 1. Files created

All under `data/research/adaptive_ensemble/r59/`:

- `live_session_gate.py`
- `one_session_activation.py`
- `credential_ipc.py`
- `restricted_live_transport.py`
- `metadata_extract.py`
- `diagnostic_worker.py`
- `diagnostic_supervisor.py`
- `real_session_entry.py`
- `test_r59_offline.py`
- `R59_METADATA_DIAGNOSTIC_PREPARATION_REPORT.md`

No `real_activation` directory was created.

## 2. Files modified

No file outside `data/research/adaptive_ensemble/r59/` was modified. R.56 source, activation, reports, and logs were not modified. Production trading code was not modified.

## 3. Exact request plan

Plan id `r59.one-get.1`. Program id `r59.real_session_entry`.

```text
GET https://api-fxtrade.oanda.com/v3/accounts/{accountID}/instruments?instruments=EUR_USD,GBP_USD,USD_JPY,AUD_USD,USD_CAD,USD_CHF
```

One request. Method GET. Host `api-fxtrade.oanda.com`. Port `443`. The instrument list and its order are fixed in the transport. There is no summary request, no pricing request, and no order or position endpoint. Redirects are rejected. Retries are rejected. A second call on the same transport is rejected. The HTTPS client timeout is five seconds. The parent session deadline is fifteen seconds and is refused if a caller asks for more. The account id is taken from the local terminal prompt after the permit has been consumed. It is not placed in the path until that point, and it is not written to the log.

## 4. Activation architecture

R.59 does not import or call the R.56 gate, and it does not read the R.56 permit.

- Source constant `REAL_SESSION_SOURCE_ENABLEMENT` in `live_session_gate.py` is `False`. No environment variable or command-line argument can change it.
- Confirmation phrase is `CONFIRM ONE INSTRUMENT METADATA SESSION`. A synthetic phrase is rejected. The receipt does not permit the network. It expires after 60 seconds and can be spent once.
- Permit schema `r59.activation.1` binds program, plan id, host, port, the single GET, the path template, and the exact query. `prepare()` checks the source gate before it creates a directory. It was not called successfully. While the gate is off it raises `REAL_OANDA_SESSION_NOT_AUTHORISED` and writes nothing.
- `consume()` is the only spend path. A missing permit raises `ACTIVATION_ABSENT` and creates nothing. A mismatched permit writes `one_session.consumed` and deletes the permit, so the slot cannot be reused. A second `consume()` raises `ACTIVATION_CONSUMED`.
- `real_session_entry.py` accepts no arguments. `run_real_session` checks the gate, checks the plan, requires the confirmation, then consumes the production permit, and only then prompts. With the gate off, the entry returns 2 before a prompt.

## 5. Credential-handling architecture

`read_environment` and `read_dotenv` always raise `REAL_CREDENTIAL_USE_NOT_AUTHORISED`. The account id is read with `input` and the token with `getpass`, and both prompts call `assert_real_session` and `assert_runtime_authorisation` first. The token must be 16 to 128 characters and must not contain whitespace or URL delimiters. The account id must match `^[0-9]{3}-[0-9]{3}-[0-9]{1,20}-[0-9]{3}$`.

The parent sends one IPC frame on the child stdin. The frame is not written to disk. The child returns a SHA-256 of the one-time capability. The parent redeems that capability once and only then writes `CAP_OK`. A harness capability cannot open a socket: the harness worker replaces `HTTPSConnection` with a function that raises. The real worker calls `assert_real_session` before it parses the frame. Logs are scanned for the account id, the token, and a bearer header. A match is replaced with `SENSITIVE_OUTPUT_BLOCKED`.

The parent calculates one monotonic session deadline at the start and does not reset it. Each readiness wait, IPC write, and worker-completion wait uses the time still remaining. Writing and flushing the initial frame, and writing and flushing the capability acknowledgement, run on a bounded wait against that same deadline. A blocked pipe is closed and the writer is joined only for a short unblock interval. The early worker-response exit wait uses the time still remaining, not a fresh five-second wait. When that time is gone, the parent terminates and reaps the worker and records `SESSION_DEADLINE` with `SESSION_INCOMPLETE`. A broken pipe or an unexpected worker exit is reaped as `CHILD_CRASHED` or `SESSION_DEADLINE`. The exception text and the IPC frame are not copied into the record. A request-timeout that fires while session time remains stays `CHILD_TERMINATED`. Cleanup is a separate bounded reap.

`record_persisted` becomes true only after an atomic replace succeeds. The parent creates the log directory, writes `session_id.json.tmp` in that directory, flushes with `fsync`, then replaces it with `session_id.json`. A failure during directory creation, write, flush, or replacement deletes the temporary file, leaves no successful record, and returns `RECORD_PERSISTENCE_FAILED` with `record_persisted` false and `SESSION_INCOMPLETE`. Exception text is not copied into the record.

## 6. Transport restrictions

`restricted_live_transport.py` builds the only request. `validate_outbound` rejects a non-GET method, a different host or port, a path other than `/v3/accounts/{accountID}/instruments`, a reordered or extended instrument list, an extra query parameter, a body, redirects, and retries. Paths containing `/orders`, `/trades`, `/positions`, `/pricing`, `/summary`, `/transactions`, `/configuration`, or `/candles` are rejected.

`LiveExchange` allows one exchange. The second raises `REQUEST_LIMIT`. A deadline already passed raises `DEADLINE_REJECTED` before a socket is constructed. A missing parent capability raises `GRANT_REJECTED` before `HTTPSConnection`. A harness object is accepted only when its marker is `R59_HARNESS_CONNECTION`. An HTTP redirect status raises `REDIRECT_REJECTED` and does not issue another request. TLS verification cannot be switched off: the live branch uses `ssl.create_default_context` and requires `CERT_REQUIRED` and hostname checks.

## 7. Sanitised output schema

Schema `r59.metadata.1`. The record stores the plan, the session id, error and session status, `network_permitted`, `network_attempted`, `broker_response_received`, and `record_persisted`. It stores `executable_order` and `order_payload` as `NOT_PRODUCED`. It stores `spread_betting_classification` and `stake_to_unit_mapping` as `NOT_VERIFIED`, and `metadata_proves_spread_betting_account` as false. `account_id_logged` and `raw_response_persisted` are false. The request is stored as the path template, not the filled account path.

For each of the six instruments, each documented field is `RETURNED`, `MISSING`, or `INVALID`. Decimal fields stay the original JSON strings. A missing financing object stays `MISSING` on `longRate`, `shortRate`, and `financingDaysOfWeek`. No missing field is written as zero. An invalid value is not copied into the log. Extra response fields are dropped. Duplicate names, unexpected names, and a set other than the six instruments reject the document. `lastTransactionID` is allowed by the official response shape and is not stored.

## 8. Offline tests and results

Command:

```text
python -B -m pytest -p no:cacheprovider --noconftest data\research\adaptive_ensemble\r59\test_r59_offline.py -q
```

Result: 12 passed, 0 failed, 7.18 seconds. Network constructors used by the parent were replaced with functions that raise. The harness child replaces `HTTPSConnection`. No test opened a socket to OANDA Practice or Live.

Independent-review corrections covered by the added tests: a failed write, a failed replacement, and a directory permission error do not leave a successful record or copy the exception text; a persistence failure is `RECORD_PERSISTENCE_FAILED` and `SESSION_INCOMPLETE`; cumulative readiness and completion stalls stay inside the overall deadline apart from bounded cleanup and record `SESSION_DEADLINE`; a malformed worker response is `MALFORMED_CHILD_RESULT`; an unexpected worker exit is `CHILD_CRASHED`; a failed cleanup is `CHILD_CLEANUP_FAILED` with the worker reaped. Blocked frame writes, blocked capability acknowledgements, and a hanging early worker response stay inside the overall deadline, leave no worker alive, and do not copy the IPC frame or the pipe error into the record. A broken pipe on the frame or the acknowledgement is `CHILD_CRASHED` and `SESSION_INCOMPLETE`.

Covered: gate file is off; entry returns before a credential prompt; absent, forged, and second use of a permit; `prepare()` writes nothing while the gate is off; host, method, path, query order, redirects, retries, deadline, and a second request; unapproved live exchange does not construct `HTTPSConnection`; missing financing stays missing; decimal `0.03330000` is unchanged; unexpected and duplicate instruments are rejected; the harness log omits the account id, the token, and a raw-body marker; a stalled child and a fault after spawn are reaped; order, pricing, and summary methods are absent; production imports and `load_dotenv` are absent.

## 9. SHA-256 of the R.59 Python files

| File | SHA-256 |
| --- | --- |
| `credential_ipc.py` | `684668340ead0b4770a1793469482664c198cc721646083579c6b17d9f3d22e7` |
| `diagnostic_supervisor.py` | `bfaf527cd9a1551b2a2e61e93299d6e5f5978795b3f0f60753d7136edd1445ea` |
| `diagnostic_worker.py` | `b0806ad27382a323601207859088c90837a5b11042035ded5deb8a70e4fa2adc` |
| `live_session_gate.py` | `2378037d15e4346edf3c421ef24b791e5993f00ade7f9ea9a1b3c2f837e74ab2` |
| `metadata_extract.py` | `259b9ec4dec03eda81cb9c9713d954ae694695cbfc04c4f8385cef73b50468ab` |
| `one_session_activation.py` | `d15778612b8bd97c65e3a826779fbbf46758f1439c3b4202968749043c6b8d90` |
| `real_session_entry.py` | `d73bccbfab02a2105969f22d68454f960240f5c2a32a5958311423cb21211e80` |
| `restricted_live_transport.py` | `d5ae2ae8bffeb07fd7c601f201a2523b20dc8023c1f20619bffafe988cf568ee` |
| `test_r59_offline.py` | `439d65a360edb8594348030745bc52e37d064c9b54468a5935c30927419a2573` |

## 10. R.56 source gate

`data/research/adaptive_ensemble/r56/phase6_connection_enablement/live_session_gate.py` line 20 is `REAL_SESSION_SOURCE_ENABLEMENT = False`. This phase did not edit that file.

## 11. R.56 consumed marker

`data/research/adaptive_ensemble/r56/phase6_connection_enablement/real_activation/one_session.consumed` is present. `one_session.permit` is absent. Neither file was modified.

## 12. R.59 source gate

`REAL_SESSION_SOURCE_ENABLEMENT = False` in `data/research/adaptive_ensemble/r59/live_session_gate.py`.

## 13. R.59 permit

No R.59 permit exists. `data/research/adaptive_ensemble/r59/real_activation` does not exist.

## 14. Known limitations

The live HTTPS branch was not executed. A passing offline suite does not show what this account's instrument payload contains. The in-memory capability is not an operating-system sandbox. The returned metadata cannot prove that the sub-account is a spread-betting account; the record says `NOT_VERIFIED` on purpose. This GET does not return a fresh GBP conversion factor. A financing object, if a later run returns one, is a snapshot and not a confirmed daily rate. `maximumPositionSize` of `0` would be stored as the returned string and is still not defined. The support enquiry from R.58 was not sent.

## 15. Recommendation for independent source review

Have a reviewer compare the nine Python hashes above with the files on disk before any later authorisation. Do not enable the R.59 gate, do not call `prepare()`, and do not run `real_session_entry.py` against OANDA as part of this phase. The entry refuses while the gate remains `False`. After review, a separate authorisation would still be required to turn the gate on, create one permit, and then run the single GET. Production trading stays stopped until that metadata and the R.58 stake confirmation both exist.
