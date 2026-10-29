"""One exact native session, admitted only by explicit terminal confirmation.

The source seal is review metadata, not permission. Fixture grants can exercise
this state machine but can never authorise an external socket or real provenance.
The owning OS user can modify code/files; this is not isolation from that user.
"""
import os
import math
from pathlib import Path
import re
import sys
import time
import uuid
from .oneshot import SPEC_HASH
from .oneshot_archive import APPROVED,Archive,Refused
from .oanda_history_manifest import encoded,decode,digest
from .confirmation_input import read_confirmation

DISABLED='AUTHENTICATED_EXECUTION_DISABLED'
PACKAGE=Path(__file__).resolve().parent
SEAL=PACKAGE/'reports/v27_activation/source_seal.json'
PREPARATION=PACKAGE/'reports/v27_activation/next_request_preparation.json'
SOURCE_FILES=('__init__.py','oneshot_authorisation.py','oneshot.py','oneshot_worker.py',
    'direct_history.py','historical_session_entry.py','oneshot_credentials.py',
    'oneshot_network.py','oneshot_archive.py','oneshot_windows.py','oneshot_bridge.py',
    'oneshot_https_fixture.py','oneshot_response.py','oanda_existing_readonly.py',
    'oanda_history_transport.py','oanda_history_manifest.py','core.py',
    'history_fixtures.py','historical_manifest.py','confirmation_input.py','token_input.py','session_namespace.py')
RIGHTS_PHRASE='I CONFIRM ACCOUNT ENTITLEMENT AND PRIVATE RESEARCH RETENTION'
ENDPOINT_PHRASE='I ACCEPT ONE NON-ACCOUNT ENDPOINT CONNECTIVITY CHECK'
FIELDS={'version','mode','root','session','spec','source','identity','issued','expires','parent','conditions','started'}
SESSION_FILES=('journal.json','grant.json','grant.claimed.json','worker.claimed.json','acquisition.json','result.json')
PREPARATION_SECONDS=15
TOKEN_SECONDS=120
ACQUISITION_SECONDS=15
LIFETIME_SECONDS=PREPARATION_SECONDS+TOKEN_SECONDS+ACQUISITION_SECONDS
_CONFIRMATIONS={}


def source_seal():
    try:
        value=decode(SEAL.read_bytes())
        if (type(value) is not dict or set(value)!={'version','baseline','spec','sources','authorises_execution'} or
            type(value['version']) is not int or value['version']!=1 or value['authorises_execution'] is not False or value['spec']!=SPEC_HASH or
            not re.fullmatch('[0-9a-f]{40}',value['baseline']) or set(value['sources'])!=set(SOURCE_FILES)):
            raise ValueError()
        for name in SOURCE_FILES:
            if digest((PACKAGE/name).read_bytes().replace(b'\r\n',b'\n'))!=value['sources'][name]:raise ValueError()
        return digest(encoded(value))
    except Exception:raise Refused('APPROVED_SOURCE_SEAL_REQUIRED') from None


def prepared_request_nonce(source):
    """Non-authorising proposal metadata; never a permit or reservation."""
    if not PREPARATION.exists():return uuid.uuid4().hex
    try:
        proposal=decode(PREPARATION.read_bytes())
        if (set(proposal)!={'version','request_id','source','spec','authorises_execution'} or
            type(proposal['version']) is not int or proposal['version']!=1 or
            proposal['authorises_execution'] is not False or proposal['source']!=source or
            proposal['spec']!=SPEC_HASH or type(proposal['request_id']) is not str or
            not re.fullmatch('[0-9a-f]{32}',proposal['request_id'])):raise ValueError()
        return proposal['request_id']
    except Exception:raise Refused('REQUEST_PREPARATION_REFUSED') from None


def confirmation_phrase(source,request_id):
    return 'CONFIRM ONE HISTORICAL EUR_USD REQUEST '+source[:12]+' '+request_id


def admitted(value):
    return type(value) is dict and value.get('mode') in ('LIVE','OFFLINE_TEST')


def _shape(cap):
    if not admitted(cap) or set(cap)!=FIELDS or type(cap['version']) is not int or cap['version'] not in (2,3) or cap['spec']!=SPEC_HASH:
        raise Refused(DISABLED)
    if (any(type(cap[k]) is not str or not re.fullmatch('[0-9a-f]{64}',cap[k]) for k in ('source','identity')) or
        type(cap['session']) is not str or not re.fullmatch('[0-9a-f]{32}',cap['session']) or
        type(cap['parent']) is not int or cap['parent']<=0 or type(cap['root']) is not str or
        type(cap['started']) not in (int,float) or not math.isfinite(cap['started']) or
        not 0<=time.monotonic()-cap['started']<=LIFETIME_SECONDS or
        type(cap['issued']) not in (int,float) or type(cap['expires']) not in (int,float) or
        cap['expires']-cap['issued']!=LIFETIME_SECONDS or not cap['issued']<=time.time()<cap['expires']):
        raise Refused('SESSION_SCOPE_OR_EXPIRY_REFUSED')
    expected='OPERATOR_ATTESTED_LIMITED_RESEARCH_RETENTION_AND_ENDPOINT_UNCERTAINTY' if cap['mode']=='LIVE' else 'SYNTHETIC_TEST_ONLY'
    from .session_namespace import session_root
    namespaced=Path(cap['root']).parent.name=='sessions'
    if namespaced and (cap['version']!=3 or Path(cap['root']).name!=cap['session']):raise Refused('SESSION_SCOPE_REFUSED')
    if cap['version']==3 and not namespaced:raise Refused('SESSION_SCOPE_REFUSED')
    if cap['conditions']!=expected or cap['mode']=='LIVE' and (os.name!='nt' or cap['version']!=3 or
            cap['root']!=str(session_root(APPROVED,cap['session']))):
        raise Refused('SESSION_SCOPE_REFUSED')
    if cap['source']!=source_seal():raise Refused('SOURCE_REVISION_CHANGED')


def _verify_reservation(value):
    """Verify exact durable grant/identity/source/state; no boolean acceptance."""
    context=value if type(value) is dict and 'reservation' in value else {}
    cap=context.get('reservation') if context else value
    _shape(cap)
    purpose=context.get('purpose','preflight')
    allowed={'reservation','purpose','grant','identity','spec','claimed_grant','worker_pid'}
    if set(context)-allowed or purpose not in ('preflight','worker_claim','credential','network','fixture_dispatch'):
        raise Refused('SESSION_CONTEXT_REFUSED')
    from .oneshot import journal
    with Archive(cap['root'],synthetic=cap['mode']=='OFFLINE_TEST') as archive:
        if archive.session_id is not None:
            from .session_namespace import require_prepared
            require_prepared(archive,cap['source'])
        if digest(encoded(archive.identity))!=cap['identity']:raise Refused('IDENTITY_CHANGED')
        claimed=archive.path('grant.claimed.json').exists()
        stored=decode(archive.read('grant.claimed.json' if claimed else 'grant.json'))
        if stored!=cap:raise Refused('GRANT_BINDING_CHANGED')
        state=journal(archive)
        if state['state']=='AUTHORISED_NOT_CONSUMED' and time.monotonic()>=cap['started']+PREPARATION_SECONDS:
            raise Refused('PREPARATION_DEADLINE_EXHAUSTED')
        if state['state'] not in ('AUTHORISED_NOT_CONSUMED','REQUEST_RESERVED','REQUEST_ATTEMPTED'):
            raise Refused('SESSION_CONSUMED')
        if state['attempts']!=(1 if state['state']=='REQUEST_ATTEMPTED' else 0):raise Refused('AMBIGUOUS_GRANT_STATE')
        if (state['state']=='AUTHORISED_NOT_CONSUMED')==claimed:raise Refused('AMBIGUOUS_GRANT_STATE')
        if any(archive.path(n+'.pending').exists() for n in SESSION_FILES):raise Refused('AMBIGUOUS_PUBLICATION')
        if state['state']=='REQUEST_RESERVED' and archive.path('worker.claimed.json').exists():raise Refused('AMBIGUOUS_WORKER_CLAIM')
        if 'identity' in context and context['identity']!=archive.identity:raise Refused('IDENTITY_CHANGED')
        for key in ('grant','claimed_grant'):
            if key in context and context[key]!=cap:raise Refused('GRANT_BINDING_CHANGED')
        if 'spec' in context and context['spec']!=SPEC_HASH:raise Refused('EXACT_REQUEST_REQUIRED')
        if purpose=='worker_claim':
            if (state['state']!='REQUEST_RESERVED' or os.getppid()!=cap['parent'] or
                time.monotonic()>=cap['started']+PREPARATION_SECONDS or archive.path('worker.claimed.json').exists()):
                raise Refused('WORKER_CLAIM_REFUSED')
        elif purpose in ('credential','network','fixture_dispatch'):
            if state['state']!='REQUEST_ATTEMPTED' or state['attempts']!=1:raise Refused('DURABLE_RESERVATION_REQUIRED')
            worker=decode(archive.read('worker.claimed.json'))
            if (set(worker)!={'session','source','pid','parent','credential_deadline'} or worker['session']!=cap['session'] or
                worker['source']!=cap['source'] or worker['parent']!=cap['parent'] or type(worker['pid']) is not int):
                raise Refused('WORKER_BINDING_REFUSED')
            token_deadline=worker['credential_deadline']
            if (type(token_deadline) not in (int,float) or not math.isfinite(token_deadline) or
                not cap['started']+TOKEN_SECONDS<=token_deadline<=cap['started']+PREPARATION_SECONDS+TOKEN_SECONDS):
                raise Refused('TOKEN_PHASE_BINDING_REFUSED')
            if purpose=='credential':
                if os.getpid()!=cap['parent'] or context.get('worker_pid',worker['pid'])!=worker['pid']:
                    raise Refused('CREDENTIAL_PROCESS_REFUSED')
                if time.monotonic()>=token_deadline or archive.path('acquisition.json').exists():
                    raise Refused('TOKEN_ENTRY_TIMEOUT_OR_CLOSED')
            elif worker['pid']!=os.getpid() or worker['parent']!=os.getppid():raise Refused('NETWORK_PROCESS_REFUSED')
            else:_acquisition(archive,cap,worker)
            if purpose=='network' and cap['mode']!='LIVE':raise Refused('FIXTURE_CANNOT_AUTHORISE_LIVE_NETWORK')
            if purpose=='fixture_dispatch' and cap['mode']!='OFFLINE_TEST':raise Refused('LIVE_CANNOT_USE_FIXTURE_BINDING')
    return cap


def require_live_reservation(value):
    try:return _verify_reservation(value)
    except Refused:raise
    except Exception:raise Refused('SESSION_STATE_UNAVAILABLE') from None


def require_role(cap,purpose,*,worker_pid=None):
    require_live_reservation(cap)
    if admitted(cap):
        context={'reservation':cap,'purpose':purpose}
        if worker_pid is not None:context['worker_pid']=worker_pid
        require_live_reservation(context)


def bind_worker(archive,cap):
    require_role(cap,'worker_claim')
    archive.put('worker.claimed.json',encoded(dict(session=cap['session'],source=cap['source'],
        pid=os.getpid(),parent=os.getppid(),credential_deadline=time.monotonic()+TOKEN_SECONDS)))


def _acquisition(archive,cap,worker):
    """Immutable post-input phase binding; required before any socket permission."""
    value=decode(archive.read('acquisition.json'))
    if (set(value)!={'session','source','parent','worker','started','seconds','deadline'} or
        value['session']!=cap['session'] or value['source']!=cap['source'] or
        value['parent']!=cap['parent'] or value['worker']!=worker['pid'] or
        any(type(value[k]) not in (int,float) or not math.isfinite(value[k]) for k in ('started','seconds','deadline')) or
        not .5<=value['seconds']<=ACQUISITION_SECONDS or cap['mode']=='LIVE' and value['seconds']!=ACQUISITION_SECONDS or
        not cap['started']<=value['started']<worker['credential_deadline'] or
        value['deadline']!=value['started']+value['seconds'] or
        not value['started']<=time.monotonic()<value['deadline']-min(1,value['seconds']/3)):
        raise Refused('ACQUISITION_PHASE_REFUSED')
    return value


def begin_acquisition(archive,cap,worker_pid,seconds):
    """Parent-only, once, after input. No state reset or second input phase."""
    started=time.monotonic()
    require_role(cap,'credential',worker_pid=worker_pid)
    if (type(archive) is not Archive or str(archive.root)!=cap['root'] or
        digest(encoded(archive.identity))!=cap['identity']):raise Refused('IDENTITY_CHANGED')
    if archive.path('acquisition.json').exists() or archive.path('acquisition.json.pending').exists():
        raise Refused('ACQUISITION_ALREADY_STARTED')
    value=dict(session=cap['session'],source=cap['source'],parent=cap['parent'],worker=worker_pid,
               started=started,seconds=seconds,deadline=started+seconds)
    worker=decode(archive.read('worker.claimed.json'))
    _shape(cap)
    if type(seconds) not in (int,float) or not .5<=seconds<=15 or cap['mode']=='LIVE' and seconds!=15:
        raise Refused('EXACT_DEADLINE_REQUIRED')
    archive.put('acquisition.json',encoded(value))
    return _acquisition(archive,cap,worker)


def acquisition_phase(archive,cap):
    return _acquisition(archive,cap,decode(archive.read('worker.claimed.json')))


def _unused(archive):
    for name in SESSION_FILES:
        if archive.path(name).exists() or archive.path(name+'.pending').exists():raise Refused('SESSION_ALREADY_PRESENT_NO_RESET')
    for directory in ('raw','validated','manifests'):
        if archive.path(directory+'/v26c_https.json').exists() or archive.path(directory+'/v26c_https.json.pending').exists():
            raise Refused('ARCHIVE_BATCH_ALREADY_PRESENT')


def _issue(archive,mode,*,started=None,confirmation=None):
    if mode=='LIVE' and (type(confirmation) is not str or confirmation not in _CONFIRMATIONS):
        raise Refused('TERMINAL_CONFIRMATION_REQUIRED')
    if type(archive) is not Archive or archive.synthetic!=(mode=='OFFLINE_TEST') or mode not in ('LIVE','OFFLINE_TEST'):
        raise Refused('GRANT_SCOPE_REFUSED')
    if mode=='LIVE' and (archive.session_id is None or archive.namespace_base!=Path(APPROVED)):
        raise Refused('APPROVED_SESSION_ROOT_REQUIRED')
    with Archive(archive.root,synthetic=mode=='OFFLINE_TEST',pin=archive.identity):pass
    _unused(archive);now=time.time();started=time.monotonic() if started is None else started
    source=source_seal()
    session=archive.session_id or uuid.uuid4().hex
    if archive.session_id is not None:
        from .session_namespace import require_prepared
        require_prepared(archive,source)
    if mode=='LIVE':
        proof=_CONFIRMATIONS.pop(confirmation,None)
        if (type(proof) is not tuple or len(proof)!=5 or
            proof[:4]!=(source,digest(encoded(archive.identity)),os.getpid(),started) or
            type(proof[4]) is not str or not re.fullmatch('[0-9a-f]{32}',proof[4])):
            raise Refused('TERMINAL_CONFIRMATION_REQUIRED')
        session=proof[4]
        if session!=archive.session_id:raise Refused('SESSION_CONFIRMATION_BINDING_REFUSED')
    cap=dict(version=3 if archive.session_id is not None else 2,mode=mode,root=str(archive.root),session=session,spec=SPEC_HASH,
        source=source,identity=digest(encoded(archive.identity)),issued=now,expires=now+LIFETIME_SECONDS,parent=os.getpid(),started=started,
        conditions='OPERATOR_ATTESTED_LIMITED_RESEARCH_RETENTION_AND_ENDPOINT_UNCERTAINTY' if mode=='LIVE' else 'SYNTHETIC_TEST_ONLY')
    archive.put('grant.json',encoded(cap))
    from .oneshot import journal_value
    archive.put('journal.json',encoded(journal_value(archive,'AUTHORISED_NOT_CONSUMED',0)))
    return cap


def issue_offline_fixture(archive):
    """Test-only writer: real archive and LIVE mode cannot enter this function."""
    if not archive.synthetic:raise Refused('SYNTHETIC_ARCHIVE_REQUIRED')
    with archive.locked():return _issue(archive,'OFFLINE_TEST')


def issue_live_interactively():
    """Never called by tests or during implementation; no noninteractive writer."""
    if os.name!='nt' or not sys.stdin.isatty() or not sys.stdout.isatty():raise Refused(DISABLED)
    source=source_seal()
    request_id=prepared_request_nonce(source)
    from .session_namespace import session_root,require_prepared
    root=session_root(APPROVED,request_id)
    with Archive(root) as archive:require_prepared(archive,source);_unused(archive);identity=archive.identity
    expected=confirmation_phrase(source,request_id)
    print('Endpoint support and account-specific retention are NOT independently verified.')
    print('Confirm only if your applicable account terms permit this request and local retention.')
    print('Prepared request ID: '+request_id)
    print('Rights attestation - type exactly: '+RIGHTS_PHRASE)
    print('Endpoint acknowledgement - type exactly: '+ENDPOINT_PHRASE)
    print('Final confirmation - type exactly: '+expected)
    if input('Rights attestation: ')!=RIGHTS_PHRASE:raise Refused('DATA_USE_CONDITIONS_NOT_CONFIRMED')
    if input('Endpoint uncertainty acknowledgement: ')!=ENDPOINT_PHRASE:raise Refused('ENDPOINT_CONDITIONS_NOT_CONFIRMED')
    print('Source seal: '+source)
    read_confirmation(expected)
    started=time.monotonic()
    if source_seal()!=source:raise Refused('SOURCE_REVISION_CHANGED')
    confirmation=uuid.uuid4().hex
    _CONFIRMATIONS[confirmation]=(source,digest(encoded(identity)),os.getpid(),started,request_id)
    try:
        with Archive(root,pin=identity) as archive,archive.locked():
            return _issue(archive,'LIVE',started=started,confirmation=confirmation)
    finally:_CONFIRMATIONS.pop(confirmation,None)


def approval_requirements(revision,source_hashes):
    """Review metadata only, never a grant or accepted reservation capability."""
    if (type(revision) is not str or not re.fullmatch('[0-9a-f]{40}',revision) or
        type(source_hashes) is not dict or not source_hashes or
        any(type(k) is not str or type(v) is not str or not re.fullmatch('[0-9a-f]{64}',v)
            for k,v in source_hashes.items())):
        raise Refused('REVIEW_METADATA_REQUIRED')
    return {'environment':'LIVE','spec_sha256':SPEC_HASH,'source_revision':revision,
            'source_hashes':dict(source_hashes),'archive_root':APPROVED,
            'attempts':1,'retries':0,'redirects':False,'pagination':False,'seconds':15,
            'requires_native_identity':True,'requires_unique_session':True,
            'authorises_execution':False}
