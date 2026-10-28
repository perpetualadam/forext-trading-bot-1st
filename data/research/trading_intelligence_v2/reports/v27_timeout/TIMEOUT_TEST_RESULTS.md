# Focused offline verification

Final local checks all passed, native Windows, synthetic inputs and disposable state only:

- Hidden token input: 7 tests.
- Exact confirmation UI: 13 tests.
- Phased admission/controller/worker integration: 24 tests.
- Existing V2.7 suite: 63 tests, unchanged.
- Existing restricted one-shot security suite: 67 tests, unchanged.

Input tests use a virtual clock to exercise 30-second and 119-second entry, exact 120-second timeout, invalid deadlines, hidden input/backspace, malformed input and interruption. Default refusal precedes console or controller access.

Integration includes an actual 16-second delayed token followed by a successful fresh acquisition window; full virtual 120-second token timeout with zero connections and durable consumed state; no network role during input; tampered phase deadline/duration/worker/source refusal before connection; expired startup without grant claim; worker crash during input; crashes around reservation/dispatch/persistence; duplicate/replayed/concurrent requests; and network deadline/fencing enforcement. Tokens remain synthetic, absent from stored evidence and logs.

The first V2.7 regression run exposed a compatibility mismatch in the newly specific timeout result. Restricting TOKEN_ENTRY_TIMEOUT to the new admitted phased protocol preserved the legacy controller's OUTCOME_UNKNOWN contract without altering its tests or safety assertions. Final existing suites are rerun unchanged.

The exact staged non-activating tree was exported independently: all 7 input tests, 13 confirmation tests and 63 native V2.7 tests passed. Staged authority/controller/worker/network files equal HEAD. Previous real session files match the read-only hash/mtime snapshot; operational source hashes and R.56 marker metadata are unchanged. Exact published SHA and CI outcome are reported in chat.
