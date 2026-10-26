# Thread containment

D.10 threads run only inside the runner child.

- Target is the real `_poller_loop`.
- Transport is the fake `requests.Session`.
- Database driver is the fake `psycopg2`.
- Configuration is synthetic.
- The long-poll wait is `RELEASE_POLL.wait(12)`. If the harness does not release it, the fake raises and the child does not spin forever.
- The real `join(2.0)` ran twice. Each child invocation is bounded by the parent timeout of 120 seconds.
- Exceptions are captured in the runner report.
- Daemon status is recorded and is not used as cleanup.
- Before harness cleanup, the runner records thread identity, alive state, stop-event state, and database globals.
- Harness cleanup then sets `_stop_event`, releases the fake poll and any blocked query, and `join`s `telegram-control` threads for at most 3 seconds.
- `reset_telegram_control_for_tests` runs only when no `telegram-control` thread is still alive.
- If a thread were still alive, the runner would record it and stop further scenarios in that child. That did not happen.
- Final `escaped_final` was empty in both modes.
- No scenario ran in the parent pytest process. The parent only starts the child.

The blocked-poll worker exited after the fake `getUpdates` was released, because `_stop_event` was already set and the production loop then ended. That exit is production loop behaviour. The harness did not kill the thread. The lifespan blocked case still had thread 3836 alive when `lifespan` returned; the harness released the fake poll afterwards and joined it.
