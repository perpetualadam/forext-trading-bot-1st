"""Closed synthetic clock bootstrap. LIVE authority and non-fixture roots refuse."""
import importlib.util
import sys
from pathlib import Path
import time


def main():
    if sys.argv[1:]!=['--bounded-worker']:raise ValueError('FIXTURE_ONLY')
    package=Path(__file__).resolve().parent
    spec=importlib.util.spec_from_file_location('tiv2',package/'__init__.py',submodule_search_locations=[str(package)])
    module=importlib.util.module_from_spec(spec);sys.modules['tiv2']=module;spec.loader.exec_module(module)
    from tiv2 import oneshot_worker as worker
    from tiv2.oneshot_archive import Archive,FIXTURES,NATIVE_FIXTURES
    from tiv2.oanda_history_manifest import decode
    from tiv2.timing_test_fixture import FixtureClock,HeaderWaitClock
    startup=worker.packet(4096);cap=startup['reservation'];root=Path(cap['root']).absolute()
    legacy='2d5f5b38efb65a0cffd5f63ad38a7da62344d653bdba84dad9438cf1eac96bf9'
    remaining='b663097a02d007a6ff055946ae1c602fe9e16c33b3f9284e17a3b5ac187dc768'
    original=dict(startup=15,token=4,request=15,session=2,spacing=1,bytes=268435456,attempts=106)
    headers=dict(startup=15,token=120,request=3,session=900,spacing=.001,bytes=268435456,attempts=106 if cap.get('catalogue')==legacy else 66)
    input_clock=cap.get('catalogue')==legacy and cap.get('limits')==original and startup.get('fault')=='crash_after_response'
    header_clock=cap.get('catalogue') in (legacy,remaining) and cap.get('limits')==headers and startup.get('fault')==''
    if (cap.get('mode')!='OFFLINE_TEST' or cap.get('version')!=4 or not (input_clock or header_clock) or 'https_fixture' not in startup or
        not any(root.is_relative_to(base) for base in (FIXTURES,NATIVE_FIXTURES))):raise ValueError('FIXTURE_ONLY')
    # Only after the closed fixture gate: no credential packet has been read.
    clock=FixtureClock(cap['started']) if input_clock else HeaderWaitClock()
    if header_clock:
        if cap['started']!=0:raise ValueError('FIXTURE_ONLY')
        clock.marker=root/'header_phase.json';clock.session=cap['session'];clock.source=cap['source']
    time.monotonic=clock.monotonic
    original_packet=worker.packet;first=True;received=False
    def packet(limit=2048):
        nonlocal first,received
        if first:first=False;return startup
        value=original_packet(limit)
        if 'credential' in value:
            if received:raise ValueError('FIXTURE_ONLY')
            received=True
            if input_clock:
                with Archive(root,synthetic=True) as ar:phase=decode(ar.read('acquisition.json'))
                if phase.get('source')!=cap['source'] or phase.get('session')!=cap['session'] or phase['deadline']-phase['started']!=2:raise ValueError('FIXTURE_ONLY')
                clock.synchronize(phase['started'])
        return value
    worker.packet=packet
    # Original audit, grant/role verification, durable reservation, synthetic
    # token validation, loopback-only sockets and one attempt remain in force.
    worker.main()


if __name__=='__main__':
    try:main()
    except (Exception,KeyboardInterrupt):
        print('TIMING_FIXTURE_REFUSED');raise SystemExit(2)
