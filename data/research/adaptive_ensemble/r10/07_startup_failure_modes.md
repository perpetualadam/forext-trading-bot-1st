# Startup failure modes

Every failure below left `offline_ready` false, `trading_ready` false, and `trading_loop_started` false. The ready phase was not recorded. No broker order was created. `database._pg_conn` stayed `None`.

| Id | Fault | Error |
| --- | --- | --- |
| F01 / I26 | Invalid fake configuration | ValueError |
| F02 / I27 | Missing broker dependency | RuntimeError, persistence closed |
| F03 / I28 | Persistence initialization fails | RuntimeError |
| F04 / I29 | Recovery provider fails | RuntimeError |
| F05 / I38 | Unreadable recovery | OrderRecoveryUnreadable |
| F06 / I30 | Broker initialization fails | RuntimeError |
| F07 / I31 | Market-data initialization fails | RuntimeError |
| F08 / I32 | Messaging initialization fails | RuntimeError |
| F09 / I33 | Health initialization fails | RuntimeError |
| F10 / I34 | Scheduler refuses | RuntimeError, no scheduler resource opened |
| F11 / I40 | Cleanup reports `close_failed:persistence` | Error visible, resources closed |
| F12 / I37 | Initialization interrupted at the broker | RuntimeError, persistence closed |
| F13 / I36 | Duplicate initialization | StartupSafetyAbort |
| F14 / I48 | Initialization after shutdown | StartupSafetyAbort, no second schedule |
| F15 / I35 | Unexpected health exception | RuntimeError |
| F16 | Scheduler awaitable returns `started` | StartupSafetyAbort |
| F17 / I21 | Missing position record | Hold remains; this is not a ready failure |
| F18 / I22 | Unknown exposure token | Flat confirmation refused |
| F19 | Unexpected application state | RuntimeError |
| F20 | Attempt to enter trading mode through the scheduler | Same refusal as F16. Trading ready stays false. |
