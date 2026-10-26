# R.80 multiprocess close results

Evidence class: executed OS processes in `test_12`. Windows and Linux. Synthetic broker. Temporary journal.

Sequence:

1. The parent completes real startup and persists one live EUR_USD row.
2. Child A runs `startup-close`. It completes its own startup, which supersedes the parent epoch, claims the close permit, and pauses inside PositionClose.
3. While A is paused, the parent reads `network_permit=1` for that close operation.
4. Child B runs `close-cold` with no recovery session. It prints `refused` and inserts nothing.
5. A is released. The recorder contains one PositionClose.
6. A later `startup-close` does not insert a second row.

The returned close state is `CLOSE_FULLY_CONFIRMED` or `CLOSE_CONFIRMATION_PENDING`. The safety assertion is the recorder count, not which of those two confirmation labels the synthetic transaction details produced.

Not executed:

- Killing the close owner before PositionClose.
- Killing the close owner after PositionClose has been entered.
- Calling `repair_abandoned_recovery` while a close permit is in flight.

Those three remain NOT_VERIFIED. The pause interleaving itself passed on both platforms.

`R80_TWO_PROCESS_CLOSE_RACE_VERIFIED`: PASS for one paused owner and one refused competitor. PARTIAL for the crash and repair rows in the phase E list.
