#!/bin/sh
# Example only. Do not merge this into the live trading-bot container.
# Persistent volume is required for the prospective store.
# Replace image/volume/path placeholders. No trading authority.
set -eu
docker run --rm \
  --name forex-macro-prospective-collect-due \
  -w /app \
  -e FORWARD_CONSENSUS_COLLECTION_ENABLED=false \
  -e MACRO_PROSPECTIVE_DATA_DIR=/app/data/research/macro/consensus_pit/prospective \
  -v forex_macro_prospective:/app/data/research/macro/consensus_pit/prospective \
  -v /path/to/forex-bot:/app \
  python:3.13-slim \
  python -m reports.decision_quality.macro_prospective_cli collect-due
