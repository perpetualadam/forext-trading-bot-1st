"""Hidden terminal input only; no admission, grant writer or network capability."""
import math
import time
from .oneshot_archive import Refused
from .oneshot_credentials import validate_token

TOKEN_ENTRY_SECONDS=120


def entry_remaining(deadline):
    if type(deadline) not in (int,float) or not math.isfinite(deadline):
        raise Refused('INVALID_TOKEN_ENTRY_DEADLINE')
    remaining=deadline-time.monotonic()
    if remaining<=0:raise Refused('TOKEN_ENTRY_TIMEOUT')
    if remaining>TOKEN_ENTRY_SECONDS:raise Refused('INVALID_TOKEN_ENTRY_DEADLINE')
    return remaining


def read_hidden_token(console,*,deadline):
    """Poll native hidden input for at most 120 seconds; never echo or retry."""
    entry_remaining(deadline)
    value=''
    print('API token: ',end='',flush=True)
    try:
        while True:
            budget=entry_remaining(deadline)
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
