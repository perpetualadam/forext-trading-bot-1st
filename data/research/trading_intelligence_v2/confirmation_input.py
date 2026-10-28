"""Exact one-line historical confirmation UI. No grant or execution authority."""
from .oneshot_archive import Refused


def read_confirmation(expected):
    """No trim, split, repair, retry or echo of the operator's response."""
    print('Required confirmation - enter exactly once, then press Enter:',flush=True)
    print(expected,flush=True)
    try:response=input('Confirmation: ')
    except EOFError:response=None
    if response!=expected:
        print('CONFIRMATION_MISMATCH - The phrase must be entered exactly once. No automatic retry.',flush=True)
        raise Refused('HISTORICAL_CONFIRMATION_REFUSED')
    print('Confirmation accepted. Continuing admission checks.',flush=True)
