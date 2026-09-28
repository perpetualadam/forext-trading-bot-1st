# MACRO PROSPECTIVE RECORDER — PERSISTENCE AUDIT

Stage 2 reported PROSPECTIVE DIRECTORY PERSISTENT: NO because
`docker-compose.yml` does not bind-mount
`data/research/macro/consensus_pit/prospective/`.

That compose fact is true. It is not the persistence status of the live recorder.

AUDIT
-----
Recorder/CLI execution location: Windows host (repo working directory).
Runtime path: `data/research/macro/consensus_pit/prospective`
Absolute host path:
`C:\Users\Brian\OneDrive\Desktop\Forext Trading Bot 1st\data\research\macro\consensus_pit\prospective`

Bot Dockerfile copies only `forex_bot/` and `main.py`. It does not copy `reports/` or the prospective tree.
Bot container `/app/data/research` contains only the existing V2 bind mount `v2_shadow`.
`PROSPECTIVE_IN_CONTAINER=NO`. `REPORTS_IN_CONTAINER=NO`.
`bot_loop` does not import the recorder or CLI.

Existing Compose volumes for `bot`:
- `./data/research/v2_shadow:/app/data/research/v2_shadow` (unchanged)

A broader `./data/research` mount would overlay unrelated research data and is not required.
A prospective bind mount would be redundant: the operator store is already the host directory.

DECISION
--------
Stage 2 "NO" was incorrect as a persistence conclusion for the actual recorder.
No Docker/Compose change. Live bot container was not restarted or recreated
(trading process has been up; recorder data is not inside it).

PROBE
-----
Isolated file `persistence_test/probe.txt` was written on the host, hashed, confirmed absent from the container, re-read with matching SHA-256, then removed.
Registered events and armed checkpoints were not modified. Real observation count remained 0.

FORWARD_CONSENSUS_COLLECTION_ENABLED remains false.
