# R.86 Snapshot Completeness

Evidence: `classify_open_positions_body` and the completeness tests. The labels are produced from synthetic bodies. They are not live OANDA responses.

| Input | Completeness | Flat verified |
| --- | --- | --- |
| Parsed positions with trades | `UNKNOWN_COMPLETENESS` | false |
| Empty `positions` list | `UNKNOWN_COMPLETENESS` | false |
| Missing `positions` key | `INCOMPLETE` | false |
| Non-object body | `INCOMPLETE` | false |
| Null body or error | `FAILED` | false |
| Cached body or pre-close chronology | `STALE` | false |
| Account id differs | `FAILED` | false |
| Duplicate trade id in one side | `INCOMPLETE` | false |
| Missing trade id on a nonzero side | `INCOMPLETE` | false |

The existing startup view can still say `COMPLETE_EMPTY` after `_interpret_open_positions`. That label was not changed, because changing recovery decisions was outside this stage. The new report does not treat `COMPLETE_EMPTY` as verified. `test_17` and `test_18` show an empty positions list is unknown and not flat.

A syntactically valid response is not complete. Completeness stays unknown until a page-completion proof exists. This repository's position fetch does not have that proof.
