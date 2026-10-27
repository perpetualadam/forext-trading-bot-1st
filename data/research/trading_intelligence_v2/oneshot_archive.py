"""Explicit archive binding. No fallback, credential loading or authorisation API.

Native identity pins are local metadata, not portable permission grants. This
protects against accidental relocation/reparse substitution, not an administrator
or the owning user deliberately rewriting state or changing this program.
"""
import contextlib
import os
from pathlib import Path
import re
from .oanda_history_manifest import encoded, decode, digest

APPROVED = r'C:\TradingResearchData\OANDA'
PACKAGE = Path(__file__).resolve().parent
FIXTURES = PACKAGE/'outputs/v26c/fixtures'
NATIVE_FIXTURES = Path(APPROVED)/'research_outputs/v26c_synthetic_sessions'
PARTS = ('raw','validated','manifests','temporary_batches','research_outputs')


class Refused(RuntimeError): pass


def safe_parts(relative):
    if not isinstance(relative,str) or not re.fullmatch(r'[A-Za-z0-9_./-]{1,180}',relative):
        raise Refused('PATH_REFUSED')
    parts=relative.split('/')
    if any(p in ('','.','..') or p.endswith('.') for p in parts):raise Refused('PATH_REFUSED')
    if any(p.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],
                                     *[f'LPT{i}' for i in range(1,10)]} for p in parts):
        raise Refused('DEVICE_PATH_REFUSED')
    return parts


class Archive:
    def __init__(self,root,*,synthetic=False,pin=None):
        self.root=Path(root).absolute();self.synthetic=synthetic;self.handles=[]
        try:
            if synthetic:
                portable=self.root==FIXTURES or self.root.is_relative_to(FIXTURES)
                native=os.name=='nt' and self.root.is_relative_to(NATIVE_FIXTURES)
                if not (portable or native):raise Refused('FIXTURE_ROOT_REFUSED')
                if native:
                    base=Archive(APPROVED)
                    self.handles.extend(base.handles);base.handles=[]
                    from . import oneshot_windows as win
                    for path in (NATIVE_FIXTURES,self.root):
                        h,_=win.identity_handle(path);self.handles.append(h);win.acl(path,win.current_sid())
            elif os.name!='nt' or str(self.root)!=APPROVED:raise Refused('APPROVED_ROOT_REQUIRED')
            for path in [*reversed(self.root.parents),self.root]:
                if path.is_symlink() or getattr(path,'is_junction',lambda:False)():raise Refused('REPARSE_REFUSED')
                if not path.is_dir():raise Refused('ARCHIVE_MISSING')
            if synthetic:
                self.identity=[self.root.stat().st_dev,self.root.stat().st_ino]
                if pin is not None and pin!=self.identity:raise Refused('IDENTITY_CHANGED')
            else:
                from . import oneshot_windows as win
                win.local_ntfs();owner=win.current_sid();identities={}
                for path in [self.root.parent,self.root,*[self.root/p for p in PARTS]]:
                    handle,identity=win.identity_handle(path);self.handles.append(handle)
                    win.acl(path,owner);identities[path.name]=identity
                self.identity={'owner':owner,'directories':identities}
                actual=decode(self.read('manifests/v26c_archive_binding.json'))
                if actual!={'version':1,'identity':self.identity}:raise Refused('IDENTITY_CHANGED')
        except BaseException:self.close();raise

    def close(self):
        if self.handles:
            from . import oneshot_windows as win
            for handle in self.handles:win.K.CloseHandle(handle)
            self.handles=[]

    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def path(self,relative):
        path=self.root.joinpath(*safe_parts(relative))
        for item in [path,*list(path.parents)[:len(path.relative_to(self.root).parts)]]:
            if item.is_symlink() or getattr(item,'is_junction',lambda:False)():raise Refused('REPARSE_REFUSED')
            if item.exists() and item.is_file() and item.stat().st_nlink!=1:raise Refused('HARDLINK_REFUSED')
        if not path.resolve().is_relative_to(self.root):raise Refused('PATH_ESCAPE')
        return path

    def read(self,relative):
        path=self.path(relative)
        if path.stat().st_size>9*1024*1024:raise Refused('FILE_TOO_LARGE')
        with path.open('rb') as stream:return stream.read(9*1024*1024+1)

    def sync(self):
        # POSIX directory fsync makes rename durable. Windows uses write-through
        # MoveFileEx below; no claim against disk firmware ignoring flushes.
        if os.name!='nt':
            fd=os.open(self.root,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)

    def rename(self,source,target,*,replace=False):
        src=self.path(source);dst=self.path(target)
        if os.name=='nt':
            from . import oneshot_windows as win
            fn=win.K.MoveFileExW;fn.argtypes=[win.w.LPCWSTR,win.w.LPCWSTR,win.w.DWORD];fn.restype=win.w.BOOL
            win.check(fn(str(src),str(dst),0x8 | (1 if replace else 0)))
        else:
            if replace:os.replace(src,dst)
            else:
                # link() is the portable local-filesystem no-clobber commit.
                # A crash before unlink leaves ambiguous hardlinks, which refuse.
                os.link(src,dst);os.unlink(src)
            for parent in {src.parent,dst.parent}:
                fd=os.open(parent,os.O_RDONLY)
                try:os.fsync(fd)
                finally:os.close(fd)

    def put(self,relative,value,*,replace=False):
        target=self.path(relative)
        if target.exists() and not replace:raise Refused('IMMUTABLE_FILE_EXISTS')
        pending=relative+'.pending';tmp=self.path(pending)
        # Any interrupted publication requires review; never reuse pending bytes.
        with tmp.open('xb') as stream:stream.write(value);stream.flush();os.fsync(stream.fileno())
        getattr(self,'after_pending',lambda name:None)(relative)
        self.rename(pending,relative,replace=replace)
        if digest(self.read(relative))!=digest(value):raise Refused('HASH_MISMATCH')
        return digest(value)

    @contextlib.contextmanager
    def locked(self):
        path=self.path('writer.lock')
        # The lock file is structural, never evidence of unused authorisation.
        with path.open('a+b') as stream:
            stream.seek(0,2)
            if not stream.tell():stream.write(b'0');stream.flush();os.fsync(stream.fileno())
            stream.seek(0)
            if os.name=='nt':
                import msvcrt
                try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                except OSError:raise Refused('BUSY') from None
            else:
                import fcntl
                try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except OSError:raise Refused('BUSY') from None
            try:yield
            finally:
                stream.seek(0)
                if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(stream,fcntl.LOCK_UN)


def prepare_native_binding():
    """Explicit non-authorising preparation, never called by acquisition.

    Refuses existing pins rather than silently rebinding changed identities.
    Caller must run as the archive owner, not relax the ACL for a sandbox.
    """
    if os.name!='nt':raise Refused('WINDOWS_REQUIRED')
    from . import oneshot_windows as win
    win.local_ntfs();root=Path(APPROVED);owner=win.current_sid();handles=[];identities={}
    try:
        for path in [root.parent,root,*[root/p for p in PARTS]]:
            h,i=win.identity_handle(path);handles.append(h);win.acl(path,owner);identities[path.name]=i
        # Reuse atomic publication without invoking the constructor's pin check.
        archive=object.__new__(Archive);archive.root=root;archive.synthetic=False;archive.handles=[]
        identity={'owner':owner,'directories':identities}
        archive.put('manifests/v26c_archive_binding.json',encoded({'version':1,'identity':identity}))
        return 'BOUND_NO_AUTHORISATION'
    finally:
        for handle in handles:win.K.CloseHandle(handle)
