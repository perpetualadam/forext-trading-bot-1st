"""Small Windows primitives for archive identity/ACL inspection and process fencing."""
import os
import ctypes as c
from ctypes import wintypes as w


class WinFailure(RuntimeError): pass


if os.name=='nt':
    K=c.WinDLL('kernel32',use_last_error=True);A=c.WinDLL('advapi32',use_last_error=True)
    signatures={
        'CreateFileW':([w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE],w.HANDLE),
        'CloseHandle':([w.HANDLE],w.BOOL),
        'GetFileInformationByHandle':([w.HANDLE,c.c_void_p],w.BOOL),
        'GetCurrentProcess':([],w.HANDLE),
        'GetDriveTypeW':([w.LPCWSTR],w.UINT),
        'GetVolumeInformationW':([w.LPCWSTR,w.LPWSTR,w.DWORD,c.c_void_p,c.c_void_p,c.c_void_p,w.LPWSTR,w.DWORD],w.BOOL),
        'LocalFree':([c.c_void_p],c.c_void_p),
        'CreateJobObjectW':([c.c_void_p,w.LPCWSTR],w.HANDLE),
        'SetInformationJobObject':([w.HANDLE,c.c_int,c.c_void_p,w.DWORD],w.BOOL),
        'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),
        'TerminateJobObject':([w.HANDLE,w.UINT],w.BOOL)}
    for name,(args,result) in signatures.items():
        fn=getattr(K,name);fn.argtypes=args;fn.restype=result
    for name,args in {
        'OpenProcessToken':[w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)],
        'GetTokenInformation':[w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)],
        'ConvertSidToStringSidW':[c.c_void_p,c.POINTER(w.LPWSTR)],
        'GetNamedSecurityInfoW':[w.LPWSTR,c.c_int,w.DWORD,c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p],
        'GetAce':[c.c_void_p,w.DWORD,c.POINTER(c.c_void_p)]}.items():
        fn=getattr(A,name);fn.argtypes=args;fn.restype=w.DWORD if name=='GetNamedSecurityInfoW' else w.BOOL


def check(ok):
    if not ok: raise WinFailure('WINDOWS_SECURITY_PRIMITIVE_FAILED')


def sid_text(pointer):
    text=w.LPWSTR();check(A.ConvertSidToStringSidW(pointer,c.byref(text)))
    try:return text.value
    finally:K.LocalFree(c.cast(text,c.c_void_p))


def current_sid():
    token=w.HANDLE();check(A.OpenProcessToken(K.GetCurrentProcess(),8,c.byref(token)))
    try:
        length=w.DWORD();A.GetTokenInformation(token,1,None,0,c.byref(length))
        buf=c.create_string_buffer(length.value);check(A.GetTokenInformation(token,1,buf,length,c.byref(length)))
        return sid_text(c.cast(buf,c.POINTER(c.c_void_p))[0])
    finally:K.CloseHandle(token)


def acl(path,owner):
    sid=c.c_void_p();dacl=c.c_void_p();sd=c.c_void_p()
    code=A.GetNamedSecurityInfoW(str(path),1,5,c.byref(sid),None,c.byref(dacl),None,c.byref(sd))
    if code:raise WinFailure('ARCHIVE_ACL_UNREADABLE')
    try:
        if sid_text(sid)!=owner or not dacl.value:raise WinFailure('ARCHIVE_OWNER_OR_DACL_REFUSED')
        count=c.c_ushort.from_address(dacl.value+4).value
        if not 1<=count<=8:raise WinFailure('ARCHIVE_DACL_REFUSED')
        principals=set()
        for i in range(count):
            ace=c.c_void_p();check(A.GetAce(dacl,i,c.byref(ace)))
            kind=c.c_ubyte.from_address(ace.value).value
            mask=c.c_uint32.from_address(ace.value+4).value
            who=sid_text(ace.value+8)
            if kind!=0 or who not in (owner,'S-1-5-18') or mask&0x1F01FF!=0x1F01FF:
                raise WinFailure('ARCHIVE_PERMISSIONS_TOO_BROAD_OR_INSUFFICIENT')
            principals.add(who)
        if principals!={owner,'S-1-5-18'}:raise WinFailure('ARCHIVE_PERMISSION_PRINCIPALS_MISSING')
    finally:K.LocalFree(sd)


class FileInfo(c.Structure):
    _fields_=[('attributes',w.DWORD),('creation',w.FILETIME),('access',w.FILETIME),('write',w.FILETIME),
        ('volume',w.DWORD),('size_high',w.DWORD),('size_low',w.DWORD),('links',w.DWORD),
        ('index_high',w.DWORD),('index_low',w.DWORD)]


def identity_handle(path):
    # FILE_LIST_DIRECTORY is intentional: metadata-only access does not engage
    # the read/delete sharing checks needed to fence directory replacement.
    handle=K.CreateFileW(str(path),0x20081,3,None,3,0x02200000,None)
    if handle in (None,c.c_void_p(-1).value):raise WinFailure('ARCHIVE_IDENTITY_UNREADABLE')
    try:
        info=FileInfo();check(K.GetFileInformationByHandle(handle,c.byref(info)))
        if info.attributes&0x400 or info.links>1:raise WinFailure('REPARSE_OR_HARDLINK_REFUSED')
        return handle,[info.volume,info.index_high,info.index_low]
    except BaseException:K.CloseHandle(handle);raise


def local_ntfs():
    name=c.create_unicode_buffer(32)
    check(K.GetDriveTypeW('C:\\')==3)
    check(K.GetVolumeInformationW('C:\\',None,0,None,None,None,name,32))
    check(name.value=='NTFS')


class Basic(c.Structure):
    _fields_=[('process_time',c.c_int64),('job_time',c.c_int64),('flags',w.DWORD),
        ('min_ws',c.c_size_t),('max_ws',c.c_size_t),('active',w.DWORD),
        ('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
class Extended(c.Structure):
    _fields_=[('basic',Basic),('io',c.c_uint64*6),('process_memory',c.c_size_t),
        ('job_memory',c.c_size_t),('peak_process',c.c_size_t),('peak_job',c.c_size_t)]


class Job:
    def __init__(self,process):
        self.handle=K.CreateJobObjectW(None,None);check(self.handle)
        try:
            settings=Extended();settings.basic.flags=0x2000
            check(K.SetInformationJobObject(self.handle,9,c.byref(settings),c.sizeof(settings)))
            check(K.AssignProcessToJobObject(self.handle,w.HANDLE(int(process._handle))))
        except BaseException:self.close();raise
    def kill(self):check(K.TerminateJobObject(self.handle,124))
    def close(self):
        if self.handle:K.CloseHandle(self.handle);self.handle=None
