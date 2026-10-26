# Child-process containment

Each D.15 mode runs in a fresh Python process with a 180-second parent timeout. The child installs guards, runs one mode, writes a JSON report, and exits. Blocked polling, overlapping start and stop, and database-lock waits run in that child, not in the parent pytest process.

Waits are event and barrier waits with explicit deadlines. The production stop join remains 2.0 seconds, so a blocked worker makes that join take about two seconds. Test joins around it are three to five seconds. There is no unbounded sleep.

If a worker is still alive, the report keeps that fact and the existing harness joins it before the child exits. A child is not reused for another mode. Final `escaped_final` was empty in the passing children. Daemon threads are not the containment mechanism.
