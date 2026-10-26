# R.67C Executive summary

1. The R.67A and R.67B contracts are consistent on the safety direction: observation is not management, management is not a close, a failed snapshot is not flat, and a local price is not a broker stop. They are not fully consistent on one close transition. An unlinked flat read must not promote `CLOSE_OUTCOME_UNKNOWN` to `CLOSE_FULLY_CONFIRMED`. That correction is C2 in `R67C_CONTRACT_CLARIFICATIONS.md`. Four further naming and evidence clarifications are recorded. The approved documents were not rewritten.

2. Invariants 1 through 25 in the test report were asserted. The seeded sweep used seed 67, 200 sequences, 12 steps, and checked the invariant function after every step.

3. All 60 numbered scenarios passed. Nine extra partial-fill, lock, and refusal tests passed. The seeded sweep passed. Windows 70 passed, 0 failed. WSL2 70 passed, 0 failed.

4. No scenario failed.

5. Live payloads, `PositionClose` idempotency, client-extension echo, decimal unit acceptance, partial allocation without `tradesClosed`, hedging permission, and account currency remain `NOT_VERIFIED`. Freshness durations were not chosen.

6. The reference model prevents a second send. A timeout, a second grant, a second submitter, and a restart all refuse another close. The operational bot was not changed and can still repeat a close after a timeout (`R66-11`).

7. A 5,000 fill of a 5,000 request against 10,000 units leaves authoritative exposure at 10,000 until a later snapshot. A 4,000 fill of a 10,000 request does not reduce the stored broker units. Retirement is refused.

8. Exposure, close-attempt state, and attribution are separate fields. A snapshot can show fewer units with attribution `UNKNOWN`. A human close during an ambiguous bot attempt can confirm flat exposure while the attempt stays in manual review and is not attributed to the bot.

9. A fallback price is `LOCAL_REFERENCE_ONLY`. It is not copied into the confirmed stop. An incomplete stop section stays `PROTECTION_UNKNOWN`.

10. Before any operational edit, correct C2 in the close lifecycle, align the single-flight index with C3, and tighten `UNPROTECTED_CONFIRMED` per C4. Do not treat reference-model passes as bot passes. Do not treat the in-memory ledger as PostgreSQL.

11. R.68 should implement stage 1 only: stop `log_only` and broker-mode import from creating a row the manage loop can delete or close. Leave the entry path blocked. Do not start stages 2 through 6 in that same change.

12. Production trading remains prohibited.

`R67_DESIGN_PARTIALLY_VALIDATED`

`REAL_NETWORK_EXECUTION_NOT_TESTED`

`POSTGRESQL_INTEGRATION_NOT_TESTED`

`MODEL_TRANSACTION_TESTED`

Production trading remains NO-GO.
