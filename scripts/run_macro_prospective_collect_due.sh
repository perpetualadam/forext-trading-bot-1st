#!/bin/sh
# Portable collect-due wrapper. No event/checkpoint logic.
# Sets the repository working directory from this script's location, then
# runs the canonical application command and exits.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
PYTHON="${MACRO_PROSPECTIVE_PYTHON:-python3}"
exec "$PYTHON" -m reports.decision_quality.macro_prospective_cli collect-due "$@"
