# R.86 Partial Close Reporting

Evidence: executed reports on the R.85 quantities. Broker bodies are synthetic. The journal remainder is an input, not a new durable write.

Fixture: original 1,000 EUR_USD BUY, confirmed closed 400, journal remainder 600, manageable 0, ratchet unchanged because the report does not touch it.

| Observation | Report |
| --- | --- |
| Parsed 600 | Broker line 600, quality unverified. Journal line 600, not confirmed. They are separate |
| Parsed 1,000 | Broker 1,000 and journal 600 differ. Journal state is not rewritten |
| Empty positions list | Not a verified flat. Journal 600 remains visible |
| Opposite short side | Broker direction SELL beside journal BUY |
| Other trade id | Both ids are present. They are not merged |
| Missing observation | Unknown line, units null |
| Failed retrieval | Unknown line, units null |
| Stale or earlier epoch | Broker quality `stale_not_current`, not authoritative |
| Incomplete body | Unknown, not complete |

No line in the partial fixture is manageable. `quarantine_released` is false. `broker_requests` is 0. The close confirmation state passed into the function is unchanged on return.

`COMPLETE` from the R.85 startup fixtures is not reused as `COMPLETE_VERIFIED`.
