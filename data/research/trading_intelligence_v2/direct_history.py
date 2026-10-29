"""Thin terminal frontend for the existing one-shot candle workflow.

No permit issuer, environment credential source, diagnostic or second downloader.
Real admission requires the exact source seal, terminal attestations and one-use grant.
"""
import sys
import time
from . import oneshot_authorisation as authority
from .oneshot import SPEC,run_once
from .oneshot_archive import APPROVED,Refused
from .oanda_existing_readonly import candle_request
from .oneshot_credentials import validate_token
from .confirmation_input import read_confirmation
from .token_input import read_hidden_token,entry_remaining

CONFIRMATION='CONFIRM ONE HISTORICAL EUR_USD REQUEST'


def render_plan():
    request=candle_request()
    return '\n'.join(['V2.7 historical connectivity proposal - not execution approval',
        'LIVE GET https://'+request['host']+request['path'],
        *[k+'='+v for k,v in request['params'].items()],
        'count omitted; one attempt; no retries, redirects, proxy or pagination',
        'Up to 120 seconds for hidden token entry; then 15 seconds for acquisition and fencing',
        'Protected storage: '+APPROVED,
        'No account ID required. No trading. No strategy evaluation.',
        'Explicit terminal admission and source-bound single-use state are required.'])


def _console():
    import os
    if os.name!='nt':raise Refused('NATIVE_WINDOWS_TERMINAL_REQUIRED')
    import msvcrt
    return msvcrt


class TerminalCredentialProvider:
    """R.56-style hidden terminal entry, with a separate bounded input phase.

    getpass's blocking Windows getwch loop cannot honour a total deadline. Poll
    the same native hidden-input primitive before getwch; never fall back to echo.
    No token field, callback, CLI/environment input or real grant is exposed.
    """
    __slots__=()
    def __repr__(self):return '<TerminalCredentialProvider TERMINAL_ONLY REDACTED>'
    def credential(self,reservation=None,*,deadline=None):
        authority.require_role(reservation,'credential')
        entry_remaining(deadline)
        if not sys.stdin.isatty() or not sys.stdout.isatty():raise Refused('INTERACTIVE_TERMINAL_REQUIRED')
        return read_hidden_token(_console(),deadline=deadline)


def run_approved_session(reservation):
    """Exact terminal-admitted entry; never invoke automatically during setup."""
    print(render_plan(),flush=True)
    if reservation is None:reservation=authority.issue_live_interactively()
    else:
        authority.require_live_reservation(reservation)
        read_confirmation(CONFIRMATION)
    root=reservation['root'] if authority.admitted(reservation) else APPROVED
    result=run_once(root,synthetic_secret=None,seconds=15.0,
        _credential_provider=TerminalCredentialProvider(),_live_reservation=reservation)
    print('Historical session: '+result['kind'],flush=True)
    return result


def launch(argv=None):
    if list(sys.argv[1:] if argv is None else argv):
        print('NO_ARGUMENTS_ALLOWED');return 2
    try:
        # Grant creation is interactive, exact-scope and refuses existing state.
        # Never invoke this entry automatically during implementation/testing.
        run_approved_session(None)
    except KeyboardInterrupt:print('SESSION_INTERRUPTED');return 2
    except Exception as error:
        allowed={authority.DISABLED,'DATA_USE_CONDITIONS_NOT_CONFIRMED','ENDPOINT_CONDITIONS_NOT_CONFIRMED',
            'HISTORICAL_CONFIRMATION_REFUSED','SESSION_ALREADY_PRESENT_NO_RESET',
            'APPROVED_SOURCE_SEAL_REQUIRED','SOURCE_REVISION_CHANGED','ARCHIVE_BATCH_ALREADY_PRESENT'}
        print(str(error) if type(error) is Refused and str(error) in allowed else 'HISTORICAL_SESSION_REFUSED');return 2
    return 0


def import_preview(raw,*,retrieved):
    """Existing validator/Bar/schema compatibility only; never start a replay."""
    from .core import timestamp
    from .oanda_history_manifest import validated,bars
    from .historical_import import SCHEMA
    rows,report=validated(raw,'EUR_USD',timestamp(SPEC['params']['from']),
        timestamp(SPEC['params']['to'])+1,retrieved)
    records=[dict(zip(SCHEMA,(r['time'],r['instrument'],'true',*r['prices']))) for r in rows]
    return dict(rows=records,bars=bars(rows),validation=report,
        independence='PREVIOUSLY_EXAMINED_CONNECTIVITY_ONLY',strategy_evaluation_permitted=False)
