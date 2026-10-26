# R.70 Pre-production Roadmap

This is a proposed order. It is not authorisation to start the next stage. Production trading stays NO-GO at every stage until a separate reviewed decision says otherwise.

Strategy profitability is not a stage in this execution sequence. It stays a separate requirement: out-of-sample history, spread and slippage, drawdown, risk-adjusted results, parameter stability, walk-forward checks, and broker execution differences. R.70 produced none of those results.

## Stage 1 — Snapshot safety

Status: implemented offline in R.70 for the OpenPositions reconcile path.

Invalid bodies do not publish and do not drive destructive reconciliation. A valid empty list is distinguished and still uses the old permitted-live disappear path. That distinction is the hand-off to Stage 3, not a fix for it.

## Stage 2 — Broker protection evidence

Verify actual broker stop orders. A missing or truncated stop section stays unknown. A local fallback price stays a local reference. `broker_sl_tp_hit` must not be treated as broker evidence while it returns false.

Do not add broker-side stops in the same change as the evidence check unless a later authorisation says so. R.70 did not add them.

## Stage 3 — Close-result safety

Require evidence of closed units for the specific operation before removing a permitted live row. A later `COMPLETE_EMPTY` snapshot may support exposure reconciliation only after this stage defines what it is allowed to do. It must not manufacture close attribution.

This is the R.67 C2 problem. R.70 stopped before implementing it.

## Stage 4 — Ambiguous-close containment

Persist a close-operation identity. A timeout stays unknown. A second close stays blocked while that identity is unresolved. `PositionClose` needs an idempotency story before any retry change. Partial fills stay open for the unfilled units.

## Stage 5 — Reconciliation concurrency

Add the smallest consistency control that covers the report dictionary and overlapping convergence, then test it with barriers. Do not start from a process-wide lock as the design. R.70's generation guard can remain the publication rule.

Wall-clock freshness still needs a real broker timestamp or equivalent. Do not invent a duration.

## Stage 6 — Restart recovery

Recover unresolved operations and broker-backed observations after restart. Positions are memory-only today. PostgreSQL integration is a separate tested change, not a migration run inside an unreviewed patch.

## Stage 7 — Risk and execution correctness

Account currency, unit conversion, margin assumptions, and broker request semantics. Sizing formulas change only under that stage's own tests. R.70 did not change them.

## Stage 8 — Full integrated regression

Synthetic broker events through the operational path, including the adverse cases from Stages 1–7, on Windows and on a Linux environment that has the declared dependencies. Do not replace pandas or the OANDA client with stubs and call that result equivalent.

## Stage 9 — Controlled broker-environment verification

A written practice-environment plan, explicitly authorised, with credentials handled outside the research notes. R.70 does not execute this stage.

## Stage 10 — Production readiness assessment

Independent review of Stages 1–9 plus the separate strategy evidence. No automatic activation. Source gates stay false unless a separate authorisation changes them. `one_session.permit` is not created by this roadmap.

## Dependency notes

Stage 3 depends on Stage 1 so that only a complete book can be discussed as flat. Stage 3 does not become safe merely because Stage 1 labelled the book `COMPLETE_EMPTY`.

Stages 4 and 6 depend on Stage 3. Stage 5 can proceed after Stage 1 and should land before restart recovery so recovered state has a defined concurrent meaning.

R.56–R.65 containment stays off this path.
