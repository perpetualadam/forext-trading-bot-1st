"""Thin terminal frontend for the existing one-shot candle workflow.

No permit issuer, environment credential source, diagnostic or second downloader.
The V2.6G admission gate remains an unconditional refusal in this stage.
"""
import sys
import time
from . import oneshot_authorisation as authority
from .oneshot import SPEC,run_once
from .oneshot_archive import APPROVED,Refused
from .oanda_existing_readonly import candle_request
from .oneshot_credentials import validate_token
from .confirmation_input import read_confirmation

CONFIRMATION='CONFIRM ONE HISTORICAL EUR_USD REQUEST'


def render_plan():
    request=candle_request()
    return '\n'.join(['V2.7 historical connectivity proposal - not execution approval',
        'LIVE GET https://'+request['host']+request['path'],
        *[k+'='+v for k,v in request['params'].items()],
        'count omitted; one attempt; no retries, redirects, proxy or pagination',
        '15-second acquisition budget includes hidden token entry and worker fencing',
        'Protected storage: '+APPROVED,
        'No account ID required. No trading. No strategy evaluation.',
        'Current entry remains AUTHENTICATED_EXECUTION_DISABLED.'])


def _console():
    import os
    if os.name!='nt':raise Refused('NATIVE_WINDOWS_TERMINAL_REQUIRED')
    import msvcrt
    return msvcrt


class TerminalCredentialProvider:
    """R.56-style hidden terminal entry, bounded by the existing worker budget.

    getpass's blocking Windows getwch loop cannot honour a total deadline. Poll
    the same native hidden-input primitive before getwch; never fall back to echo.
    No token field, callback, CLI/environment input or real grant is exposed.
    """
    __slots__=()
    def __repr__(self):return '<TerminalCredentialProvider DISABLED REDACTED>'
    def credential(self,reservation=None,*,deadline=None):
        authority.require_live_reservation(reservation)
        from .oneshot_network import remaining
        remaining(deadline)
        if not sys.stdin.isatty() or not sys.stdout.isatty():raise Refused('INTERACTIVE_TERMINAL_REQUIRED')
        console=_console();value=''
        print('API token: ',end='',flush=True)
        try:
            while True:
                budget=remaining(deadline)
                if not console.kbhit():time.sleep(min(.01,budget));continue
                character=console.getwch()
                if character=='\x03':raise KeyboardInterrupt()
                if character in ('\r','\n'):
                    if not 16<=len(value)<=128:raise Refused('CREDENTIAL_INPUT_REFUSED')
                    return validate_token(value)
                if character=='\b':value=value[:-1];continue
                if len(character)!=1 or not character.isascii() or not character.isprintable():
                    raise Refused('CREDENTIAL_INPUT_REFUSED')
                value+=character
                if len(value)>128:raise Refused('CREDENTIAL_INPUT_REFUSED')
        finally:
            value='';print('',flush=True)


def run_approved_session(reservation):
    """Future admitted entry; no current invocation can obtain such admission."""
    print(render_plan(),flush=True)
    authority.require_live_reservation(reservation)
    read_confirmation(CONFIRMATION)
    result=run_once(APPROVED,synthetic_secret=None,seconds=15.0,
        _credential_provider=TerminalCredentialProvider(),_live_reservation=reservation)
    print('Historical session: '+result['kind'],flush=True)
    return result


def launch(argv=None):
    if list(sys.argv[1:] if argv is None else argv):
        print('NO_ARGUMENTS_ALLOWED');return 2
    try:
        # No grant loader or issuer is supplied. The immutable admission gate
        # refuses before confirmation, token prompt, worker or network activity.
        run_approved_session(None)
    except KeyboardInterrupt:print('SESSION_INTERRUPTED');return 2
    except Exception:
        print(authority.DISABLED);return 2
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
