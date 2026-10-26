# R.75 Remaining Risks

## Carried limitations

- `BROKER_ENFORCED_IDEMPOTENCY_NOT_VERIFIED`. The journal can refuse a second claim. OANDA was not asked to reject a duplicate HTTP close, and a proxy retry after the request left the process is outside the SQLite transaction.
- `SQLITE_POWER_LOSS_DURABILITY_NOT_VERIFIED`.
- `LINUX_INTEGRATION_NOT_VERIFIED` for any path that imports `oandapyV20`. The journal suite did pass on WSL.
- `REAL_NETWORK_EXECUTION_NOT_TESTED`.
- `POSTGRESQL_INTEGRATION_NOT_TESTED`.

## R.75 gaps

1. `bot_loop.py` does not call `recover_managed_book`. A restarted process does not reload durable rows until some other caller does. Management of a restored position is therefore not yet ordered ahead of the live loop.
2. Live entry does not persist a position, because `open_position` does not receive a verified broker trade id. A restart before the first guarded close has nothing durable to restore. No trade id was invented to fill that gap.
3. If `claim_network_permit` commits and the client is then missing, the permit is consumed and no request is sent. A later close of that trade stays blocked until an operator reconciles it.
4. Profit-protection log watermark `profit_protection_last_logged_mfe` is not durable. An inactive position can be restored with its stored zeros. An active position with NULL ratchet fields is quarantined. Continuous protection across restart is claimed only when those fields were stored.
5. The memory book still holds one row per symbol. A second trade on that symbol is quarantined rather than represented.
6. Legacy tests under `tests/` that call `_place_market_order_sync` without a permit will fail if pytest is run. They were not updated.

## R.66 items still open

- R66-03: `broker_sl_tp_hit` remains false in `live_manage.py`. Protection evidence still does not authorise a close.
- R66-07: sizing currency is unchanged. Formulas were not edited.
- R66-10 and R66-11: duplicate closes are refused by the journal on the guarded path and on the old `execute_trade` live path. Broker-enforced suppression is still unverified.
- R66-16: outside this stage.

## Not a production approval

`DATA_ONLY_MODE_NOT_PROVEN_SAFE` remains from earlier stages. This stage does not change it. Production trading is NO-GO.
