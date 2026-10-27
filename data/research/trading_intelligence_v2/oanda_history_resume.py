"""Research files only. Hash-verified commits are authoritative, progress is an index."""
from contextlib import contextmanager
from pathlib import Path
import os
from .core import ResearchRejected
from .oanda_history_manifest import digest,encoded,decode

BASE=Path(__file__).resolve().parent/'outputs/v26'


class Store:
    def __init__(self,root,max_bytes=2*1024**3):
        self.root=Path(root).absolute();self.max_bytes=max_bytes
        if not self.root.is_relative_to(BASE.absolute()) or type(max_bytes) is not int or not 1<=max_bytes<=2*1024**3:
            raise ResearchRejected('RESEARCH_STORAGE_ROOT_OR_BUDGET_REFUSED')
        self.safe(self.root);self.root.mkdir(parents=True,exist_ok=True)

    def safe(self,path):
        path=Path(path).absolute()
        if not path.is_relative_to(BASE.absolute()): raise ResearchRejected('PATH_ESCAPE')
        for p in (path,*path.parents):
            if p==BASE.parent: break
            if p.is_symlink() or getattr(p,'is_junction',lambda:False)():
                raise ResearchRejected('LINK_OR_JUNCTION_REFUSED')
        if path.resolve()!=path: raise ResearchRejected('NONCANONICAL_STORAGE_PATH')
        return path

    def path(self,name):
        path=self.safe(self.root/name)
        if not path.is_relative_to(self.root): raise ResearchRejected('PATH_ESCAPE')
        return path

    @contextmanager
    def locked(self):
        with self.path('writer.lock').open('a+b') as f:
            if f.tell()==0: f.write(b'0');f.flush();os.fsync(f.fileno())
            f.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError: raise ResearchRejected('ACQUISITION_WRITER_BUSY') from None
            try: yield
            finally:
                f.seek(0)
                if os.name=='nt': msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
                else: fcntl.flock(f,fcntl.LOCK_UN)

    def read(self,name):
        path=self.path(name)
        if path.stat().st_size>16*1024*1024: raise ResearchRejected('STORED_FILE_TOO_LARGE')
        return path.read_bytes()

    def usage(self):
        total=0
        for p in self.root.rglob('*'):
            self.safe(p)
            if p.is_file(): total+=p.stat().st_size
        return total

    def publish(self,name,raw,*,replace_index=False):
        if replace_index and name not in ('progress.json','manifest.json'):
            raise ResearchRejected('IMMUTABLE_BATCH_REPLACEMENT_REFUSED')
        path=self.path(name);pending=self.path(name+'.pending')
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if self.read(name)==raw: return
            if not replace_index: raise ResearchRejected('IMMUTABLE_FILE_CONFLICT')
        if self.usage()+len(raw)>self.max_bytes: raise ResearchRejected('DISK_BUDGET_EXCEEDED')
        if pending.exists():
            if pending.read_bytes()!=raw: raise ResearchRejected('AMBIGUOUS_LOCAL_PUBLICATION_REQUIRES_REVIEW')
        else:
            with pending.open('xb') as f:
                f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(pending,path)
        if os.name!='nt':
            fd=os.open(path.parent,os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)

    def verify(self,name,sha256):
        raw=self.read(name)
        if digest(raw)!=sha256: raise ResearchRejected('STORED_HASH_MISMATCH')
        return raw
