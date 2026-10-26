# R.80 authority-loss interleavings

Evidence class: executed fault injection in `test_08` and `test_09`, plus the multiprocess pause and kill. No network request. The second check is `forex_bot/oanda_exec.py` lines 449–450 and 544–545.

| Interleaving | What happened | Submission |
| --- | --- | --- |
| Authority valid at adapter entry, then lost before `api.request` | `test_08` lets the first `live_management_permitted()` pass, claims the entry permit, then the second call bumps the durable epoch and returns false | Prevented. OrderCreate count is 0. A later submit still sends nothing. The permit stays consumed |
| Authority changes inside `api.request` | `test_09` counts the OrderCreate, then bumps the epoch before the response is handled | Already submitted. Count stays 1. Finalisation remains durable. Memory publication is refused. A later submit adds no call |
| Owner paused inside the request | `test_11` and `test_12` | The one request is in flight. The competitor inserts nothing |
| Process killed inside the entry request | `test_13` | The recorder insert never runs. The successor does not submit. The broker result of a real request in that window is unknown |
| Response cannot be persisted | `test_05` arms `before_commit` after the counted request | Outcome stays `ENTRY_OUTCOME_AMBIGUOUS`. No second reservation |
| Close authority lost after the permit and before the request | Same recheck exists at line 449 | NOT_VERIFIED as its own close test. The entry test exercises the same function |

Distinctions that must stay separate:

- Submission prevented before the request: `test_08`.
- Request already submitted: `test_09`.
- Outcome ambiguous: `test_02` and `test_05`.
- Response received but not persisted: `test_05`.
- Owner superseded: the later startup in `test_11` and `test_12`.
- Durable permit consumed: `network_permit=1` while the close owner is paused.
- Duplicate submission prevented: recorder and call counts stay at one, or at zero when the request was refused.
- Broker-side duplicate rejection: NOT_VERIFIED.

The authority check and `api.request` are separate operations. Passing the check does not make the HTTP write atomic.

`R80_AUTHORITY_LOSS_INTERLEAVINGS_TESTED`: PASS for the entry before-request and during-request cases. PARTIAL for the close-only and pre-claim rows.
