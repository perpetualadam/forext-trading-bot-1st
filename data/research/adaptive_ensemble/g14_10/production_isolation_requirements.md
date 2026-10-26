# Production isolation requirements

Classification: `PRODUCTION_ISOLATION_UNVERIFIED`

No acquisition environment exists, so none of these separations was demonstrated. They remain requirements for any later design.

A future environment must be shown, not assumed, to be separate from:

- The running container `forexttradingbot1st-bot-1`. Its G.14.2 identity was not refreshed and must not be changed.
- Any production PostgreSQL container or volume. Neither was opened.
- Operational safety-state mounts. Not opened.
- Shadow-state mounts. Not opened.
- Broker credentials. Not read. The two backup filenames were not opened.
- Database credentials. Not read.
- Production environment variables. Not printed.
- The Docker socket. Not opened.
- Host administrator rights. This process is not elevated. A future stage must not take elevation unless that stage's own approval says so.
- Other projects, including Consensus Forecast. Not traversed.
- A full repository mount. The destination denylist in `tests/g14_4_acquire.py` rejects the repository path. That is code, not a mount policy inside a guest that does not exist.

The environment must not execute the forex application, must not run its startup hooks, and must not enable live trading. It must not depend on stopping the production container. A different container command on the same historical daemon is not evidence of harmlessness.

`DOCKER_DAEMON_CONTEXT_BEHAVIOUR_UNVERIFIED` and the historical fact of one daemon with a running production container are why a container is not assumed to meet this list.

Live-order authorisation stays BLOCKED with reason `operator_preflight_blocked`. The six strategies stay inactive. Those states were not read from safety files in this stage. They are preserved by not being touched.
