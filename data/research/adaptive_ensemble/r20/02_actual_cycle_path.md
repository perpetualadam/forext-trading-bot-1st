# Actual cycle path

The production scheduler is `run_bot`, which calls `_cycle_symbols`, which calls `evaluate`. That scheduler was not started.

`evaluate(symbol, dependencies)` is the safe single-iteration entry. When a dependency object is supplied, it returns `dispatch_production_iteration`, which calls `evaluate_one_instrument_iteration`. The same `evaluate` function is what `_cycle_symbols` uses for one symbol. The offline driver called `evaluate` directly. It did not call `run_bot` or `_evaluate_impl`.

Shared order inside one iteration:

1. Session, then a read of the exposure hold and the local position book.
2. An open position returns `position_already_open` before strategy, reservation, or dispatch.
3. Otherwise an exposure or unresolved hold returns before strategy.
4. Live permission blocks unless the isolated simulation context is set. That context does not create production authority.
5. `select_strategy`, `AIEnsemble.vote`, and `RLAgent.decide`.
6. Market checks, account gate, sizing, portfolio risk, and the R.18 eligibility seal.
7. Reservation, then the inert recording adapter. The production adapter is referenced and not called.

External services replaced only at the boundary: the recording broker, the in-memory order and exposure maps, and the injected synthetic quote. PostgreSQL, OANDA, and the network were not used.
