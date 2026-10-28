# Confirmation verification

Focused offline runs on native Windows, 2026-10-28:

- `python -I -S -B tests/test_v27_confirmation_input.py`: 13 passed.
- `v26d_run.py --native-activation-tests`: 18 passed.
- `v26d_run.py --native-v27-tests`: 63 passed.
- `v26d_run.py --native-v26g-tests`: 67 passed.

UI coverage includes correct once-only acceptance; concatenated/separated duplicates; embedded newlines; empty/EOF input; wrong request ID/seal; untrimmed whitespace; acceptance ordering; no rejected-input echo; rejection before controller or credential access; and default admission refusal before any input. The controller is the only downstream worker/network entry, so its non-invocation prevents those paths.

Admission regressions exercise exact terminal attestations, duplicate rejection before grant writing, synthetic durable one-use claims, concurrent controllers, replay refusal, malformed/ambiguous state, deadline and worker fencing, source/identity bindings, hidden input, token redaction, TLS validation, exact GET restriction and refusal of trading routes. Network integration uses synthetic credentials and loopback fixtures only.

Read-only before/after inspection confirms real archive session/batch files remain absent and R.56 marker metadata unchanged. AST comparison confirms grant writer, reservation/role validators, worker binding and unused-state checks unchanged; the local interactive function delegates its existing equality check to the helper. No real grant, credential entry or OANDA request occurred.

The exact staged publication tree was independently exported: 13 UI tests and all 63 V2.7 native tests passed. The first minimal export lacked seven baseline source files read by AST assertions; supplying those unchanged index files resolved all five missing-file errors. Staged authorisation and transport sources equal the published baseline; only the disabled frontend UI integration is staged. Exact-SHA GitHub CI is checked after publication and its outcome reported in chat.
