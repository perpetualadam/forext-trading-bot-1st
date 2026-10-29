"""Thin terminal entry to the existing bounded worker branch; never run by tests."""
import importlib.util
from pathlib import Path
import sys

def launch():
    if sys.argv[1:]:raise SystemExit('NO_ARGUMENTS_ALLOWED')
    package=Path(__file__).resolve().parent
    if 'tiv2' not in sys.modules:
        spec=importlib.util.spec_from_file_location('tiv2',package/'__init__.py',submodule_search_locations=[str(package)])
        module=importlib.util.module_from_spec(spec);sys.modules['tiv2']=module;spec.loader.exec_module(module)
    from tiv2.bounded_acquisition import run,issue_interactively,CATALOGUE_HASH
    from tiv2.oneshot_authorisation import source_seal
    from tiv2.oneshot_archive import Archive,APPROVED,Refused
    from tiv2.direct_history import TerminalCredentialProvider
    from tiv2.oanda_history_manifest import decode
    proposal=decode((package/'reports/v28c/acquisition_preparation.json').read_bytes())
    if (set(proposal)!={'version','session','source','catalogue','authorises_execution'} or proposal['version']!=1 or
        proposal['authorises_execution'] is not False or proposal['source']!=source_seal() or proposal['catalogue']!=CATALOGUE_HASH):raise Refused('BOUNDED_PROPOSAL_REFUSED')
    with Archive(Path(APPROVED)/'sessions'/proposal['session']) as archive:
        cap=issue_interactively(archive)
        result=run(archive,cap,TerminalCredentialProvider())
    print('Historical acquisition: '+result['kind'])
    return 0 if result['kind']=='DONE' else 2

if __name__=='__main__':
    try:raise SystemExit(launch())
    except (KeyboardInterrupt,Exception):
        print('BOUNDED_HISTORICAL_SESSION_REFUSED');raise SystemExit(2)
