"""A recycled OS thread ID must not hide correct worker replacement."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from current_lifecycle_fixtures import fresh_live_worker


def worker(alive):
    return SimpleNamespace(ident=7, is_alive=lambda: alive)


def test_recycled_ident_requires_a_distinct_live_worker_and_stopped_predecessor():
    old, new = worker(False), worker(True)
    assert old.ident == new.ident
    assert fresh_live_worker(old, new) is True
    assert fresh_live_worker(new, new) is False
    assert fresh_live_worker(worker(True), new) is False
    assert fresh_live_worker(old, worker(False)) is False


@pytest.mark.parametrize("previous,current", [(None, worker(True)), (worker(False), None)])
def test_absent_workers_cannot_satisfy_replacement(previous, current):
    assert fresh_live_worker(previous, current) is False
