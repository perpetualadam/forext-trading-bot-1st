"""Non-authorising, identity-bound namespaces inside the existing archive."""
import contextlib
import os
from pathlib import Path
import re
from .oneshot_archive import Archive,APPROVED,PARTS,Refused
from .oanda_history_manifest import encoded,decode,digest
from .oneshot import SPEC,SPEC_HASH


def session_root(base,session_id):
    if type(session_id) is not str or not re.fullmatch('[0-9a-f]{32}',session_id):raise Refused('SESSION_ID_REFUSED')
    return Path(base).absolute()/'sessions'/session_id


def request_metadata(archive,source):
    if archive.session_id is None:raise Refused('SESSION_REQUIRED')
    if type(source) is not str or not re.fullmatch('[0-9a-f]{64}',source):raise Refused('SOURCE_SEAL_REQUIRED')
    return dict(version=1,session=archive.session_id,identity=archive.identity,source=source,
                spec=SPEC,spec_sha256=SPEC_HASH,authorises_execution=False,
                limits=dict(preparation_seconds=15,token_seconds=120,acquisition_seconds=15,
                            attempts=1,retries=0,redirects=False,proxy=False,pagination=False,fallback=False))


def require_prepared(archive,source):
    if archive.session_id is None:raise Refused('SESSION_REQUIRED')
    if decode(archive.read('request.json')).get('kind')=='BOUNDED_106':
        from .bounded_acquisition import require_prepared as check
        return check(archive,source)
    if encoded(decode(archive.read('request.json')))!=encoded(request_metadata(archive,source)):raise Refused('SESSION_REQUEST_BINDING_REFUSED')
    if archive.path('request.json.pending').exists() or archive.path('session_binding.json.pending').exists():
        raise Refused('AMBIGUOUS_SESSION_PREPARATION')


def _checked_directory(path,*,create):
    if create:path.mkdir() # Exclusive creation; never adopt an existing session.
    if path.is_symlink() or getattr(path,'is_junction',lambda:False)() or not path.is_dir():raise Refused('SESSION_DIRECTORY_REFUSED')
    if os.name=='nt':
        from . import oneshot_windows as win
        h,_=win.identity_handle(path)
        try:win.acl(path,win.current_sid())
        finally:win.K.CloseHandle(h)


def prepare_session(base,session_id,source,*,synthetic=False,_bounded_rights=None):
    """Create binding and immutable proposal only. No grant/journal or reset."""
    root=session_root(base,session_id)
    from .oneshot_authorisation import source_seal
    if source!=source_seal():raise Refused('SOURCE_REVISION_CHANGED')
    with Archive(base,synthetic=synthetic) as parent:
        if parent.session_id is not None:raise Refused('NESTED_SESSION_REFUSED')
        container=parent.path('sessions')
        try:container.mkdir()
        except FileExistsError:pass
        _checked_directory(container,create=False)
        # Retain identity handles on the container while creating descendants.
        handle=None
        if os.name=='nt':
            from . import oneshot_windows as win
            handle,_=win.identity_handle(container)
        try:
            try:_checked_directory(root,create=True)
            except FileExistsError:raise Refused('SESSION_ID_ALREADY_EXISTS') from None
            root_handle=None
            if os.name=='nt':root_handle,_=win.identity_handle(root)
            try:
                for name in PARTS:_checked_directory(root/name,create=True)
                with Archive(root,synthetic=synthetic,_bind_session=True) as archive:
                    archive.put('session_binding.json',encoded(dict(version=1,session=session_id,identity=archive.identity)))
                    if _bounded_rights is None:
                        archive.put('request.json',encoded(request_metadata(archive,source)))
                    else:
                        from .bounded_acquisition import metadata,budget_guard
                        archive.publication_guard=lambda relative,value:budget_guard(archive,len(value),accounting=relative in ('journal.json','result.json'))
                        archive.put('rights_scope.json',encoded(_bounded_rights))
                        archive.put('request.json',encoded(metadata(archive,source)))
                with Archive(root,synthetic=synthetic) as archive:require_prepared(archive,source)
            finally:
                if root_handle is not None:win.K.CloseHandle(root_handle)
        finally:
            if handle is not None:win.K.CloseHandle(handle)
    return root


@contextlib.contextmanager
def acquisition_lock(archive):
    """One active namespaced acquisition, including token entry and fencing."""
    if archive.session_id is None:raise Refused('SESSION_REQUIRED')
    with Archive(archive.namespace_base,synthetic=archive.synthetic) as parent:
        guard=parent.locked('historical_acquisition.lock')
        try:lease=guard.__enter__()
        except Refused as error:
            if str(error)=='BUSY':raise Refused('GLOBAL_ACQUISITION_BUSY') from None
            raise
        try:
            if parent.path('historical_acquisition.blocked.json').exists() or parent.path('historical_acquisition.blocked.json.pending').exists():
                raise Refused('GLOBAL_FENCING_UNCONFIRMED')
            yield lease
        finally:guard.__exit__(None,None,None)


def block_unfenced(archive,cap):
    if cap['session']!=archive.session_id or cap['root']!=str(archive.root):raise Refused('CROSS_SESSION_RESULT_REFUSED')
    with Archive(archive.namespace_base,synthetic=archive.synthetic) as parent:
        parent.put('historical_acquisition.blocked.json',encoded(dict(session=cap['session'],reason='FENCING_UNCONFIRMED')))


def publish_result(archive,cap,result):
    """Fixed metadata only; never include a credential, exception text or body."""
    require_prepared(archive,cap['source'])
    if cap['session']!=archive.session_id or cap['root']!=str(archive.root) or cap['identity']!=digest(encoded(archive.identity)):
        raise Refused('CROSS_SESSION_RESULT_REFUSED')
    if result['kind'] not in {'DONE','REFUSED','OUTCOME_UNKNOWN','TOKEN_ENTRY_TIMEOUT','FENCING_UNCONFIRMED','DEADLINE_OVERRUN'}:
        raise Refused('RESULT_KIND_REFUSED')
    from .oneshot import journal
    state=journal(archive)
    value=dict(version=1,session=archive.session_id,source=cap['source'],spec=SPEC_HASH,
               kind=result['kind'],worker_exited=result['worker_exited'],journal_state=state['state'],attempts=state['attempts'],
               grant_sha256=digest(archive.read('grant.claimed.json')))
    archive.put('result.json',encoded(value))
