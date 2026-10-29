"""Independent sessions, synthetic credentials and loopback only. No LIVE issuer."""
import copy
import hashlib
import os
import queue
from pathlib import Path
import threading
import time
import uuid
import subprocess
import sys
import importlib.util
import io
import tempfile

if __name__=='__main__':
    package=Path(__file__).resolve().parent
    spec=importlib.util.spec_from_file_location('tiv2',package/'__init__.py',submodule_search_locations=[str(package)])
    module=importlib.util.module_from_spec(spec);sys.modules['tiv2']=module;spec.loader.exec_module(module)
    __package__='tiv2'
from unittest.mock import patch
from . import test_v27_activation as previous
from . import oneshot_authorisation as authority
from . import oneshot_worker as worker
from .oneshot import journal,run_once,SPEC_HASH
from .oneshot_archive import Archive,Refused
from .oneshot_windows import WinFailure
from .session_namespace import prepare_session,session_root,require_prepared,acquisition_lock,publish_result,block_unfenced
from .oneshot_bridge import SyntheticCredentialProvider
from .https_test_server import LocalHTTPS
from .oanda_history_manifest import encoded,decode,digest

previous.legacy.NATIVE=globals().get('NATIVE',False)
ISOLATION_RECORDS=('grant.json','grant.claimed.json','journal.json','worker.claimed.json',
                   'acquisition.json','result.json','request.json','session_binding.json')


def file_open_probe():
    """Test-only child: real audit hooks and real opens on disposable fixtures.

    No grant validation/creation or HTTP path is invoked. The input roots must
    be inside the existing synthetic fixture trees; stdout never contains data.
    """
    from .oneshot_archive import FIXTURES,NATIVE_FIXTURES
    os.environ.clear()
    value=decode(sys.stdin.buffer.readline(4097))
    if set(value)!={'active','legacy','sibling','alias'}:raise ValueError('FIXTURE_PACKET_REQUIRED')
    roots={name:Path(value[name]).resolve() for name in ('active','legacy','sibling')}
    for root in roots.values():
        if not any(root.is_relative_to(base.resolve()) for base in (FIXTURES,NATIVE_FIXTURES)):
            raise ValueError('SYNTHETIC_ROOT_REQUIRED')
    if roots['sibling'].parent!=roots['legacy']/'sessions':raise ValueError('FIXTURE_LAYOUT_REQUIRED')
    if roots['active']!=roots['legacy'] and roots['active'].parent!=roots['legacy']/'sessions':raise ValueError('FIXTURE_LAYOUT_REQUIRED')
    if value['alias'] not in ('','junction','hardlink'):raise ValueError('FIXTURE_ALIAS_REQUIRED')
    worker.configure_session_reads(roots['legacy'])
    worker.configure_session_reads(roots['active']) # Deliberately exercise replacement, not union.
    worker.ACTIVE_ROOT=roots['active'];worker.LIVE_POLICY=None;worker.LOOPBACK_PORT=None
    sys.addaudithook(worker.audit)
    failures=[];counts={'allowed':0,'denied':0}
    def attempt(label,operation,allowed):
        try:operation()
        except PermissionError as error:
            actual=False
            if str(error) not in {'WORKER_READ_REFUSED','WORKER_WRITE_REFUSED','WORKER_MUTATION_REFUSED','WORKER_HARDLINK_REFUSED'}:
                failures.append(label+':unexpected_os_permission')
        else:actual=True
        counts['allowed' if actual else 'denied']+=1
        if actual!=allowed:failures.append(label+':scope_mismatch')
    def builtin_read(path):
        with open(path,'rb') as stream:stream.read(1)
    def io_read(path):
        with io.open(path,'rb') as stream:stream.read(1)
    def os_read(path):
        descriptor=os.open(path,os.O_RDONLY)
        try:os.read(descriptor,1)
        finally:os.close(descriptor)
    def append(path):
        with open(path,'ab') as stream:stream.write(b'SYNTHETIC_UNEXPECTED_WRITE')
    for area in ('active','legacy','sibling'):
        own=roots[area]==roots['active']
        for name in ISOLATION_RECORDS:
            path=roots[area]/name
            for operation,reader in (('builtin',builtin_read),('pathlib',Path.read_bytes),('io',io_read),('os',os_read)):
                attempt(area+':'+name+':'+operation,lambda path=path,reader=reader:reader(path),own)
            if not own:
                attempt(area+':'+name+':append',lambda path=path:append(path),False)
                attempt(area+':'+name+':truncate',lambda path=path:path.write_bytes(b'SYNTHETIC_SUBSTITUTION'),False)
                attempt(area+':'+name+':replace',lambda path=path:os.replace(roots['active']/'replacement.json',path),False)
    if value['alias']:
        paths=([roots['active']/'sibling_alias'/name for name in ISOLATION_RECORDS] if value['alias']=='junction'
               else [roots['active']/'foreign_hardlink.json'])
        for path in paths:
            attempt('alias:read',lambda path=path:builtin_read(path),False)
            attempt('alias:write',lambda path=path:append(path),False)
    # Explicit shared resources are code and non-authorising review metadata.
    for path in (Path(worker.__file__),Path(os.__file__),worker.SOURCE_SEAL):
        attempt('shared:'+path.name,lambda path=path:builtin_read(path),True)
    print(__import__('json').dumps(dict(counts=counts,failures=failures),sort_keys=True))
    return 1 if failures else 0


class NamespacedHTTPS(previous.AdmissionHTTPS):
    def probe_layout(self,portable=False):
        from .oneshot_archive import FIXTURES
        if portable:
            temporary=tempfile.TemporaryDirectory(prefix='read_isolation_',dir=FIXTURES)
            base=Path(temporary.name)
            assert base.resolve().is_relative_to(FIXTURES.resolve())
            self.addCleanup(temporary.cleanup)
        else:base=self.fixture(authorised=False).root
        container=base/'sessions';container.mkdir()
        active=container/uuid.uuid4().hex;sibling=container/uuid.uuid4().hex
        active.mkdir();sibling.mkdir()
        for root in (base,active,sibling):
            for name in ISOLATION_RECORDS:(root/name).write_bytes(encoded(dict(synthetic=True,record=name,owner=root.name)))
        (active/'replacement.json').write_bytes(b'SYNTHETIC_REPLACEMENT_ONLY')
        return base,active,sibling

    def run_open_probe(self,base,active,sibling,alias=''):
        roots=set((base,active,sibling))
        before={str(root/name):(root/name).read_bytes() for root in roots for name in ISOLATION_RECORDS}
        executable=getattr(sys,'_base_executable',sys.executable) if os.name=='nt' else sys.executable
        command=[executable,'-I','-S','-B',str(Path(__file__).resolve()),'--fixture-open-probe']
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                 env={'SystemRoot':r'C:\Windows'} if os.name=='nt' else {},close_fds=True)
        try:
            out,error=process.communicate(encoded(dict(active=str(active),legacy=str(base),sibling=str(sibling),alias=alias)),timeout=10)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=3)
        self.assertEqual(process.returncode,0,error.decode(errors='replace'))
        result=decode(out);self.assertEqual(result['failures'],[],result)
        self.assertGreater(result['counts']['allowed'],0);self.assertGreater(result['counts']['denied'],0)
        self.assertEqual(before,{name:Path(name).read_bytes() for name in before})

    def test_actual_file_opens_deny_legacy_and_sibling_native(self):
        self.run_open_probe(*self.probe_layout())

    def test_actual_file_opens_deny_package_fixture_siblings(self):
        self.run_open_probe(*self.probe_layout(portable=True))

    def test_actual_file_opens_preserve_explicit_legacy_scope(self):
        base,active,sibling=self.probe_layout()
        self.run_open_probe(base,base,sibling)

    def test_actual_file_opens_deny_junction_alias(self):
        base,active,sibling=self.probe_layout();alias=active/'sibling_alias'
        if os.name=='nt':
            import _winapi
            _winapi.CreateJunction(str(sibling),str(alias))
        else:alias.symlink_to(sibling,target_is_directory=True)
        try:self.run_open_probe(base,active,sibling,'junction')
        finally:
            assert alias.parent==active and (alias.is_symlink() or alias.is_junction())
            if alias.is_symlink():alias.unlink()
            else:os.rmdir(alias)

    def test_actual_file_opens_deny_cross_session_hardlink(self):
        base,active,sibling=self.probe_layout();alias=active/'foreign_hardlink.json'
        os.link(sibling/'grant.claimed.json',alias)
        try:self.run_open_probe(base,active,sibling,'hardlink')
        finally:
            assert alias.parent==active and alias.stat().st_nlink==2
            alias.unlink()
    def prepared(self,base=None):
        base=self.fixture(authorised=False) if base is None else base
        root=prepare_session(base.root,uuid.uuid4().hex,authority.source_seal(),synthetic=True)
        archive=Archive(root,synthetic=True);self.addCleanup(archive.close)
        return archive

    def admitted_fixture(self):
        archive=self.prepared()
        return archive,authority.issue_offline_fixture(archive)

    def test_legacy_unknown_evidence_preserved_byte_for_byte(self):
        legacy=self.fixture(authorised=False)
        evidence={'grant.claimed.json':dict(session='SYNTHETIC_LEGACY_CONSUMED'),
                  'journal.json':dict(version=1,state='REQUEST_ATTEMPTED',spec=SPEC_HASH,attempts=1),
                  'worker.claimed.json':dict(pid=123,parent=456),
                  'result.json':dict(kind='OUTCOME_UNKNOWN')}
        for name,value in evidence.items():legacy.put(name,encoded(value))
        before={n:legacy.read(n) for n in evidence}
        archive=self.prepared(legacy);cap=authority.issue_offline_fixture(archive)
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            result=self.run_session(archive,cap,server)
            self.assertEqual(result['kind'],'DONE',result)
        self.assertEqual(before,{n:legacy.read(n) for n in evidence})
        self.assertEqual(decode(legacy.read('result.json'))['kind'],'OUTCOME_UNKNOWN')

    def test_namespace_creation_confers_no_authority(self):
        archive=self.prepared()
        for name in ('grant.json','grant.claimed.json','journal.json','worker.claimed.json','acquisition.json','result.json'):
            self.assertFalse(archive.path(name).exists())
        metadata=decode(archive.read('request.json'));self.assertIs(metadata['authorises_execution'],False)
        with self.assertRaises(Refused):authority.require_live_reservation(metadata)
        with self.assertRaisesRegex(Refused,'TERMINAL_CONFIRMATION_REQUIRED'):
            authority._issue(archive,'LIVE',confirmation='0'*32)

    def test_duplicate_session_id_refused_without_replacing_any_bytes(self):
        archive=self.prepared();before={p.name:p.read_bytes() for p in archive.root.iterdir() if p.is_file()}
        with self.assertRaisesRegex(Refused,'SESSION_ID_ALREADY_EXISTS'):
            prepare_session(archive.namespace_base,archive.session_id,authority.source_seal(),synthetic=True)
        self.assertEqual(before,{p.name:p.read_bytes() for p in archive.root.iterdir() if p.is_file()})

    def test_traversal_and_malformed_ids_refused(self):
        base=self.fixture(authorised=False)
        for value in ('../legacy','a/b','A'*32,'a'*31,'a'*33,'..',None,'C:\\escape'):
            with self.subTest(value=value),self.assertRaises(Refused):session_root(base.root,value)
        self.assertFalse(base.path('sessions').exists())

    def test_stale_prepared_request_cannot_issue_a_fixture_grant(self):
        archive=self.prepared();proposal=decode(archive.read('request.json'));proposal['source']='0'*64
        archive.put('request.json',encoded(proposal),replace=True)
        with self.assertRaises(Refused):authority.issue_offline_fixture(archive)
        self.assertFalse(archive.path('grant.json').exists())

    def test_stale_source_refused_before_directory_creation(self):
        base=self.fixture(authorised=False);sid=uuid.uuid4().hex
        with self.assertRaisesRegex(Refused,'SOURCE_REVISION_CHANGED'):
            prepare_session(base.root,sid,'0'*64,synthetic=True)
        self.assertFalse((base.root/'sessions').exists())

    def test_noncanonical_metadata_types_cannot_substitute_for_fixed_contract(self):
        archive=self.prepared();original=decode(archive.read('request.json'))
        for change in ({'version':True},{'authorises_execution':0},{'limits':dict(original['limits'],attempts=True)}):
            archive.put('request.json',encoded(dict(original,**change)),replace=True)
            with self.assertRaises(Refused):authority.issue_offline_fixture(archive)
            self.assertFalse(archive.path('grant.json').exists())

    def test_immutable_spec_cannot_be_broadened(self):
        archive=self.prepared();proposal=decode(archive.read('request.json'));proposal['spec']['method']='POST'
        archive.put('request.json',encoded(proposal),replace=True)
        with self.assertRaises(Refused):authority.issue_offline_fixture(archive)
        self.assertFalse(archive.path('grant.json').exists())

    def test_cross_session_grant_substitution_refused(self):
        base=self.fixture(authorised=False);a=self.prepared(base);b=self.prepared(base)
        first=authority.issue_offline_fixture(a);second=authority.issue_offline_fixture(b)
        b.put('grant.json',a.read('grant.json'),replace=True)
        with self.assertRaises(Refused):authority.require_live_reservation(second)
        bad=copy.deepcopy(first);bad.update(root=str(b.root),session=b.session_id,identity=digest(encoded(b.identity)))
        with self.assertRaises(Refused):authority.require_live_reservation(bad)
        self.assertFalse(a.path('grant.claimed.json').exists());self.assertFalse(b.path('grant.claimed.json').exists())

    def test_cross_session_journal_substitution_refused(self):
        base=self.fixture(authorised=False);a=self.prepared(base);b=self.prepared(base)
        authority.issue_offline_fixture(a);second=authority.issue_offline_fixture(b)
        b.put('journal.json',a.read('journal.json'),replace=True)
        with self.assertRaisesRegex(Refused,'CROSS_SESSION_JOURNAL_REFUSED'):journal(b)
        with self.assertRaises(Refused):authority.require_live_reservation(second)

    def test_cross_session_identity_and_request_substitution_refused(self):
        base=self.fixture(authorised=False);a=self.prepared(base);b=self.prepared(base)
        b.put('request.json',a.read('request.json'),replace=True)
        with self.assertRaises(Refused):require_prepared(b,authority.source_seal())
        b.put('session_binding.json',a.read('session_binding.json'),replace=True)
        with self.assertRaises(Refused):Archive(b.root,synthetic=True)

    def test_stale_worker_cannot_publish_to_successor_session(self):
        base=self.fixture(authorised=False);a=self.prepared(base);b=self.prepared(base)
        cap=authority.issue_offline_fixture(a)
        with self.assertRaisesRegex(Refused,'CROSS_SESSION_RESULT_REFUSED'):
            publish_result(b,cap,dict(kind='OUTCOME_UNKNOWN',worker_exited=True))
        with patch.object(worker,'ACTIVE_ROOT',a.root):
            with self.assertRaises(PermissionError):worker.audit('open',(str(b.path('result.json')),'w',os.O_WRONLY|os.O_CREAT))
            with self.assertRaises(PermissionError):worker.audit('os.rename',(str(a.path('result.json')),str(b.path('result.json'))))
        self.assertFalse(b.path('result.json').exists())

    def test_two_session_concurrency_preserves_authority_and_global_exclusion(self):
        base=self.fixture(authorised=False);a=self.prepared(base);b=self.prepared(base)
        first=authority.issue_offline_fixture(a);second=authority.issue_offline_fixture(b)
        entered=threading.Event();release=threading.Event();results=[]
        def credential(_):entered.set();self.assertTrue(release.wait(5));return self.secret
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            def execute():
                with patch.object(SyntheticCredentialProvider,'credential',credential):results.append(self.run_session(a,first,server))
            thread=threading.Thread(target=execute);thread.start()
            try:
                self.assertTrue(entered.wait(5))
                blocked=self.run_session(b,second,server)
                self.assertEqual(blocked['kind'],'GLOBAL_ACQUISITION_BUSY',blocked)
                self.assertEqual(journal(b)['attempts'],0);self.assertTrue(b.path('grant.json').exists())
                self.assertFalse(b.path('grant.claimed.json').exists());self.assertFalse(b.path('result.json').exists())
            finally:release.set();thread.join(16)
            self.assertFalse(thread.is_alive());self.assertEqual(results[0]['kind'],'DONE',results)
            # Separate explicit test invocation after the global lock is released;
            # the controller never queues or automatically retries a busy grant.
            other=self.run_session(b,second,server)
            self.assertEqual(other['kind'],'DONE',other);self.assertEqual(len(server.requests),2)
        for archive in (a,b):
            self.assertEqual(journal(archive)['state'],'SESSION_CONSUMED')
            self.assertEqual(decode(archive.read('result.json'))['session'],archive.session_id)
            self.assertTrue(archive.path('manifests/v26c_https.json').exists())

    def test_unconfirmed_fence_blocks_other_sessions_without_reset(self):
        base=self.fixture(authorised=False);a=self.prepared(base);b=self.prepared(base)
        cap=authority.issue_offline_fixture(a);block_unfenced(a,cap)
        with self.assertRaisesRegex(Refused,'GLOBAL_FENCING_UNCONFIRMED'):
            with acquisition_lock(b):self.fail('global lock must refuse')

    def test_real_windows_junction_cannot_be_adopted_as_session(self):
        if os.name!='nt':return
        import _winapi
        base=self.fixture(authorised=False);target=self.fixture(authorised=False)
        base.path('sessions').mkdir();link=base.path('sessions')/uuid.uuid4().hex
        _winapi.CreateJunction(str(target.root),str(link))
        try:
            self.assertTrue(link.is_junction())
            with self.assertRaises((Refused,WinFailure)):Archive(link,synthetic=True)
            with self.assertRaises(Refused):prepare_session(base.root,link.name,authority.source_seal(),synthetic=True)
        finally:
            assert link.parent==base.root/'sessions' and link.is_junction()
            os.rmdir(link) # Junction only; target and its data are preserved.

    def test_symbolic_link_flag_is_refused_before_use(self):
        archive=self.prepared();original=Path.is_symlink
        with patch.object(Path,'is_symlink',lambda path:path==archive.root or original(path)):
            with self.assertRaises(Refused):Archive(archive.root,synthetic=True)

    def test_two_actual_worker_processes_cannot_claim_same_session(self):
        from .oneshot import reserve,WORKER
        archive,cap=self.admitted_fixture()
        with archive.locked():reserve(archive,_live_reservation=cap)
        processes=[];jobs=[];messages=queue.Queue()
        executable=getattr(sys,'_base_executable',sys.executable) if os.name=='nt' else sys.executable
        with LocalHTTPS(self.cert,self.key,secret=self.secret) as server:
            startup=dict(root=str(archive.root),pin=archive.identity,fault='',live_reservation=cap,
                         deadline=time.monotonic()+10,https_fixture=server.binding())
            try:
                for _ in range(2):
                    process=subprocess.Popen([executable,'-I','-S','-B',str(WORKER),'--worker'],stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env={'SystemRoot':r'C:\Windows'} if os.name=='nt' else {},close_fds=True)
                    processes.append(process)
                    if os.name=='nt':
                        from .oneshot_windows import Job
                        jobs.append(Job(process))
                    process.stdin.write(encoded(startup));process.stdin.flush()
                    def read_first(child):messages.put((child,decode(child.stdout.readline(4097))))
                    threading.Thread(target=read_first,args=(process,),daemon=True).start()
                first=messages.get(timeout=5);second=messages.get(timeout=5)
                self.assertEqual(sorted([first[1]['kind'],second[1]['kind']]),['REFUSED','RESERVED'])
                winner=next(child for child,message in (first,second) if message['kind']=='RESERVED')
                # No acquisition marker exists. Even a synthetic credential cannot dispatch.
                winner.stdin.write(encoded({'credential':self.secret}));winner.stdin.flush()
                for process in processes:process.wait(timeout=5)
                self.assertEqual(journal(archive)['attempts'],1)
                self.assertEqual(decode(archive.read('worker.claimed.json'))['pid'],winner.pid)
                self.assertEqual((server.connections,len(server.requests)),(0,0))
            finally:
                for job in jobs:job.kill();job.close()
                for process in processes:
                    if process.poll() is None:process.kill()
                    process.wait(timeout=3)
                    for stream in (process.stdin,process.stdout):stream.close()

    def test_real_windows_junction_container_refused(self):
        if os.name!='nt':return
        import _winapi
        base=self.fixture(authorised=False);target=self.fixture(authorised=False);link=base.root/'sessions'
        _winapi.CreateJunction(str(target.root),str(link))
        try:
            with self.assertRaises(Refused):prepare_session(base.root,uuid.uuid4().hex,authority.source_seal(),synthetic=True)
        finally:
            assert link.parent==base.root and link.is_junction()
            os.rmdir(link)

    def test_owner_acl_check_failures_cannot_open_session(self):
        if os.name!='nt':return
        from . import oneshot_windows as win
        archive=self.prepared()
        with patch.object(win,'current_sid',return_value='S-1-5-18'):
            with self.assertRaises(WinFailure):Archive(archive.root,synthetic=True)
        with patch.object(win,'acl',side_effect=WinFailure('ARCHIVE_PERMISSIONS_TOO_BROAD_OR_INSUFFICIENT')):
            with self.assertRaises(WinFailure):Archive(archive.root,synthetic=True)

    def test_namespace_binding_pending_is_not_authority(self):
        archive=self.prepared();archive.path('request.json.pending').write_bytes(b'{}')
        with self.assertRaises(Refused):authority.issue_offline_fixture(archive)
        self.assertFalse(archive.path('grant.json').exists())

    def test_insecure_session_file_acl_is_refused(self):
        if os.name!='nt':return
        from . import oneshot_windows as win
        archive=self.prepared();original=win.acl;request=archive.root/'request.json'
        def check(path,owner):
            if Path(path)==request:raise WinFailure('ARCHIVE_PERMISSIONS_TOO_BROAD_OR_INSUFFICIENT')
            return original(path,owner)
        with patch.object(win,'acl',side_effect=check),self.assertRaises(WinFailure):
            archive.read('request.json')


if __name__=='__main__':
    if sys.argv[1:]!=['--fixture-open-probe']:raise SystemExit('FIXTURE_PROBE_ONLY')
    raise SystemExit(file_open_probe())
