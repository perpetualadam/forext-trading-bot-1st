"""Bounded diagnostic codes only. No exception text, bodies, headers or secrets."""
import ssl
import re
from .oneshot_archive import Refused
from .core import ResearchRejected
from .oanda_history_manifest import encoded,decode,digest
REASONS=frozenset({'CONNECT_TIMEOUT','CONNECT_REFUSED','DNS_FAILURE','TLS_FAILURE','TLS_TIMEOUT','HTTP_STATUS_REJECTED','RESPONSE_HEADERS_TIMEOUT','RESPONSE_BODY_TIMEOUT','RESPONSE_TRUNCATED','RESPONSE_SCHEMA_INVALID','ARCHIVE_PUBLICATION_FAILED','WORKER_CRASHED','WORKER_DEADLINE_EXCEEDED','SESSION_DEADLINE_EXCEEDED','STARTUP_DEADLINE_EXCEEDED','TOKEN_ENTRY_TIMEOUT','GLOBAL_LOCK_LOST','SOURCE_BINDING_INVALID','ACCOUNTING_INCONSISTENT','FENCING_UNCONFIRMED','USER_INTERRUPTED','UNKNOWN_FAILURE'})
STAGES=frozenset({'STARTUP','TOKEN','RESERVATION','CONNECT','DNS','TLS','TRANSMIT','HEADERS','BODY','HTTP','VALIDATION','ARCHIVE','ACCOUNTING','SUPERVISION','CLEANUP','UNKNOWN'})
CAUSES=frozenset({'ResearchRejected','Refused','Other'})

class Failure(Refused):
    def __init__(self,reason,stage,legacy_kind='Refused'):
        self.reason=reason if reason in REASONS else 'UNKNOWN_FAILURE'
        self.stage=stage if stage in STAGES else 'UNKNOWN'
        self.legacy_kind=legacy_kind if legacy_kind in CAUSES else 'Other'
        super().__init__('REDACTED_DIAGNOSTIC_FAILURE')


def classify(error,stage):
    if isinstance(error,Failure):return error
    kind='ResearchRejected' if isinstance(error,ResearchRejected) else 'Refused' if isinstance(error,Refused) else 'Other'
    reason='UNKNOWN_FAILURE'
    if isinstance(error,KeyboardInterrupt):reason='USER_INTERRUPTED'
    elif isinstance(error,ssl.SSLError):reason='TLS_FAILURE'
    elif isinstance(error,TimeoutError):reason={'CONNECT':'CONNECT_TIMEOUT','TLS':'TLS_TIMEOUT','HEADERS':'RESPONSE_HEADERS_TIMEOUT','BODY':'RESPONSE_BODY_TIMEOUT'}.get(stage,'UNKNOWN_FAILURE')
    elif isinstance(error,ConnectionRefusedError):reason='CONNECT_REFUSED'
    elif stage=='ARCHIVE' and isinstance(error,(OSError,Refused)):reason='ARCHIVE_PUBLICATION_FAILED'
    elif isinstance(error,(ResearchRejected,Refused)):
        # Compare only exact known in-repository codes; never persist this string.
        code=str(error)
        if code in {'REDIRECT_REFUSED','HTTP_RETRY_EXHAUSTED','HTTP_REQUEST_REFUSED'}:reason='HTTP_STATUS_REJECTED'
        elif code=='INCOMPLETE_HTTP_BODY':reason='RESPONSE_TRUNCATED'
        elif code=='GLOBAL_LOCK_LOST':reason='GLOBAL_LOCK_LOST'
        elif code in {'APPROVED_SOURCE_SEAL_REQUIRED','CATALOGUE_CHANGED','BOUNDED_IDENTITY_CHANGED','BOUNDED_PREPARATION_REFUSED','STALE_BOUNDED_APPROVAL','IDENTITY_CHANGED'}:reason='SOURCE_BINDING_INVALID'
        elif code in {'BOUNDED_JOURNAL_REFUSED','WINDOW_STATE_REFUSED','WINDOW_ATTEMPT_INCONSISTENT','PREDECESSOR_NOT_COMPLETED','OUT_OF_ORDER_WINDOW','REQUEST_BUDGET_INCONSISTENT','AMBIGUOUS_PUBLICATION','SPENT_MARKER_CORRUPTED','COMPLETED_WINDOW_CORRUPTED'}:reason='ACCOUNTING_INCONSISTENT'
        elif code=='TOKEN_ENTRY_TIMEOUT':reason='TOKEN_ENTRY_TIMEOUT'
        elif code in {'WINDOW_DEADLINE','DEADLINE_EXHAUSTED'}:reason='WORKER_DEADLINE_EXCEEDED'
        elif code=='BOUNDED_SESSION_DEADLINE':reason='SESSION_DEADLINE_EXCEEDED'
        elif stage=='VALIDATION':reason='RESPONSE_SCHEMA_INVALID'
    return Failure(reason,stage,kind)

class Context:
    """Only current fixed stage is retained; never captures function arguments."""
    def __init__(self,notify=None):self.stage='UNKNOWN';self.notify=notify
    def set(self,stage):
        if stage not in STAGES:raise Failure('UNKNOWN_FAILURE','UNKNOWN')
        self.stage=stage
        if self.notify:self.notify(stage)
    def call(self,stage,operation):
        self.set(stage)
        try:return operation()
        except Exception as error:raise classify(error,stage) from None


def record(cap,reason,stage,index):
    if (type(cap.get('session')) is not str or not re.fullmatch('[0-9a-f]{32}',cap['session']) or
        any(type(cap.get(k)) is not str or not re.fullmatch('[0-9a-f]{64}',cap[k]) for k in ('source','catalogue'))):raise Refused('DIAGNOSTIC_BINDING_REFUSED')
    if reason not in REASONS or stage not in STAGES or index is not None and (type(index) is not int or not 0<=index<106):
        raise Refused('DIAGNOSTIC_METADATA_REFUSED')
    return dict(version=1,session=cap['session'],source=cap['source'],catalogue=cap['catalogue'],reason=reason,stage=stage,window_index=index,outcome='UNKNOWN_NO_RETRY',retry_allowed=False)


def read_verified(ar):
    if ar.path('diagnostic.json.pending').exists() or ar.path('result.json.pending').exists():raise Refused('DIAGNOSTIC_PUBLICATION_AMBIGUOUS')
    result=decode(ar.read('result.json'));raw=ar.read('diagnostic.json');value=decode(raw)
    if (result.get('diagnostic_sha256')!=digest(raw) or result.get('failure_reason')!=value.get('reason') or result.get('failure_stage')!=value.get('stage') or set(value)!={'version','session','source','catalogue','reason','stage','window_index','outcome','retry_allowed'} or
        type(value['version']) is not int or value['version']!=1 or value!=record(dict(session=result.get('session'),source=result.get('source'),catalogue=result.get('catalogue')),value['reason'],value['stage'],value['window_index'])):
        raise Refused('DIAGNOSTIC_INTEGRITY_REFUSED')
    return value
