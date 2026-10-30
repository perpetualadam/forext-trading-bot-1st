"""Deterministic clock for one OFFLINE_TEST timing oracle, never LIVE code.

The original 4-second input and 2-second acquisition limits remain unchanged.
Native filesystem scheduling is not a logical clock. Real sockets keep their
timeouts, and a 15-second wall watchdog expires the entire fixture fail-closed.
All real-clock deadline/crash/integration tests run without this fixture.
"""
import contextlib
import math
import json
from pathlib import Path
import time
from unittest.mock import patch

REAL_MONOTONIC=time.monotonic
WALL_LIMIT=15
LIFETIME=15+4+2


class FixtureClock:
    def __init__(self,start=None,*,_wall=REAL_MONOTONIC):
        self.wall=_wall;self.wall_start=_wall()
        # Integer logical epoch keeps the exact 1/2/4-second oracle independent
        # of host uptime and binary exponent-boundary subtraction rounding.
        self.start=0 if start is None else start
        if type(self.start) not in (int,float) or not math.isfinite(self.start):raise ValueError('FIXTURE_CLOCK_REFUSED')
        self.value=self.start
    def monotonic(self):
        elapsed=self.wall()-self.wall_start
        if elapsed>=WALL_LIMIT:return self.start+LIFETIME+1+elapsed
        return self.value
    def advance(self,seconds):
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<0:raise ValueError('FIXTURE_CLOCK_REFUSED')
        self.value+=seconds
    def synchronize(self,value):
        if type(value) not in (int,float) or not math.isfinite(value) or not self.value<=value<=self.start+4:raise ValueError('FIXTURE_CLOCK_REFUSED')
        self.value=value


class HeaderWaitClock:
    """Freeze fixture setup, then measure real elapsed header-wait time.

    The marker is published only after the TLS server parsed the actual request
    and checked the durable ATTEMPTED reservation. No counter or I/O is mocked.
    """
    def __init__(self,*,_wall=REAL_MONOTONIC):
        self.wall=_wall;self.wall_start=_wall();self.origin=None
        self.marker=None;self.session=None;self.source=None;self.entered=False
    def expired(self):return 15+120+900+1+max(0,self.wall()-self.wall_start)
    def monotonic(self):
        now=self.wall()
        if now-self.wall_start>=WALL_LIMIT:return self.expired()
        if self.origin is None and self.marker is not None and self.marker.exists():
            try:
                v=json.loads(self.marker.read_bytes())
                if (set(v)!={'version','session','source','origin','state','http_attempts'} or
                    v['version']!=1 or v['session']!=self.session or v['source']!=self.source or
                    v['state']!='ATTEMPTED' or v['http_attempts']!=1 or
                    type(v['origin']) not in (int,float) or not math.isfinite(v['origin']) or not 0<=v['origin']<=self.wall()):raise ValueError()
                self.origin=v['origin']
            except Exception:return self.expired()
        return 0 if self.origin is None else max(0,self.wall()-self.origin)
    def bind(self,archive,server):
        from .oneshot_archive import Refused
        from .oanda_history_manifest import decode,encoded
        if not archive.synthetic or archive.session_id is None or server.scenario!='delayed_headers':raise Refused('HEADER_FIXTURE_ONLY')
        self.session=archive.session_id;self.source=decode(archive.read('request.json'))['source']
        self.marker=archive.path('header_phase.json')
        if self.marker.exists() or archive.path('header_phase.json.pending').exists():raise Refused('HEADER_FIXTURE_ALREADY_USED')
        def observed():
            if self.entered:raise Refused('HEADER_FIXTURE_ALREADY_USED')
            state=decode(archive.read('journal.json'));w=state['windows'][state['next']]
            if state['state']!='ACTIVE' or w['state']!='ATTEMPTED' or w['http_attempts']!=1:raise Refused('HEADER_RESERVATION_REQUIRED')
            self.origin=self.wall()
            archive.put('header_phase.json',encoded(dict(version=1,session=self.session,source=self.source,origin=self.origin,state='ATTEMPTED',http_attempts=1)))
            self.entered=True
        server.header_phase=observed


@contextlib.contextmanager
def deterministic_input_clock():
    from . import oneshot
    clock=FixtureClock()
    with patch.object(time,'monotonic',clock.monotonic),patch.object(oneshot,'WORKER',Path(__file__).with_name('timing_test_worker.py')):
        yield clock


@contextlib.contextmanager
def synchronized_header_wait():
    from . import oneshot
    clock=HeaderWaitClock()
    with patch.object(time,'monotonic',clock.monotonic),patch.object(oneshot,'WORKER',Path(__file__).with_name('timing_test_worker.py')):
        yield clock
