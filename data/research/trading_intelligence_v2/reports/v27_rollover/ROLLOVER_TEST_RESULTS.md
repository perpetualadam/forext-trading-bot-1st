# Corrected read-isolation verification

Final runtime source seal: 39bd36d8a7f7b6abb7bbbcb28739bb39f1fb75d80a779fa2809ba59252d7ab9e.

All 220 focused native Windows tests passed with zero failures, errors or skips: the original 215 plus five actual-file-open isolation tests.

- v26d_run.py --native-rollover-tests: 46 (original 41 plus five new cases).
- v26d_run.py --native-activation-tests: 24.
- v26d_run.py --native-v27-tests: 63.
- v26d_run.py --native-v26g-tests: 67.
- tests/test_v27_token_input.py: 7.
- tests/test_v27_confirmation_input.py: 13.

The five new tests run child Python processes with the real worker audit hook installed. Disposable synthetic legacy, active and sibling records use grant.json, grant.claimed.json, journal.json, worker.claimed.json, acquisition.json, result.json, request.json and session_binding.json. Real open(), pathlib, io.open() and os.open() attempts verify denial of foreign reads. Append, truncate and os.replace attempts verify that foreign bytes cannot be modified or substituted. Snapshots confirm all fixture records remain unchanged.

The cases cover protected native fixtures, fixtures physically inside PACKAGE/outputs, explicit legacy operation, a real Windows junction alias and a real cross-session hardlink. Positive controls confirm own-session reads and the documented shared code/review resources still work. Bootstrap reconfiguration from legacy to namespace proves that the old allowlist is replaced. Denials must originate from the worker's fixed audit refusal codes, not an incidental OS ACL error.

The original namespace, grant/journal/result substitution, two-process race, two-session/global-lock, unconfirmed-fencing, crash, UNKNOWN/replay, source/identity/ACL, 120-second entry, fresh acquisition deadline, TLS, exact GET, broker-write refusal and no-operational-import cases remain in place. Existing test assertions are retained. No real API endpoint, credential getter or LIVE issuer is exercised.

The old 215 tests alone missed the legacy read allowlist and broad PACKAGE exception. The new actual-open tests close that coverage gap; simulated audit events are not the sole evidence. Consumed-session hashes and UNKNOWN classification remain unchanged.
