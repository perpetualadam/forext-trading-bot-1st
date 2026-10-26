"""Handle-relative destination creation. No network and no real wheelhouse."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path
from typing import Any

FILE_LIST_DIRECTORY = 0x0001
FILE_ADD_FILE = 0x0002
FILE_ADD_SUBDIRECTORY = 0x0004
FILE_READ_ATTRIBUTES = 0x0080
FILE_READ_DATA = 0x0001
FILE_WRITE_DATA = 0x0002
FILE_TRAVERSE = 0x0020
SYNCHRONIZE = 0x00100000
FILE_SHARE_ALL = 0x00000007
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_OPEN = 1
FILE_CREATE = 2
FILE_DIRECTORY_FILE = 0x00000001
FILE_NON_DIRECTORY_FILE = 0x00000040
FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
FILE_OPEN_REPARSE_POINT = 0x00200000
INVALID_HANDLE = wintypes.HANDLE(-1).value
INITIAL_LOOKUP_RACE = "INITIAL_PATH_LOOKUP_NOT_ATOMIC"
_RESERVED_DEVICES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{index}" for index in range(1, 10)}
    | {f"lpt{index}" for index in range(1, 10)}
)


class FilesystemRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _UnicodeString(ctypes.Structure):
    _fields_ = (
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", ctypes.c_wchar_p),
    )


class _ObjectAttributes(ctypes.Structure):
    _fields_ = (
        ("Length", wintypes.ULONG),
        ("RootDirectory", wintypes.HANDLE),
        ("ObjectName", ctypes.POINTER(_UnicodeString)),
        ("Attributes", wintypes.ULONG),
        ("SecurityDescriptor", ctypes.c_void_p),
        ("SecurityQualityOfService", ctypes.c_void_p),
    )


class _IoStatus(ctypes.Structure):
    _fields_ = (("Status", ctypes.c_ulonglong), ("Information", ctypes.c_ulonglong))


class _ByHandle(ctypes.Structure):
    _fields_ = (
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    )


def _kernel32():
    library = ctypes.WinDLL("kernel32", use_last_error=True)
    library.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    library.CreateFileW.restype = wintypes.HANDLE
    library.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ByHandle)]
    library.GetFileInformationByHandle.restype = wintypes.BOOL
    library.WriteFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    library.WriteFile.restype = wintypes.BOOL
    library.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    library.ReadFile.restype = wintypes.BOOL
    library.SetFilePointer.argtypes = [
        wintypes.HANDLE,
        ctypes.c_long,
        ctypes.POINTER(ctypes.c_long),
        wintypes.DWORD,
    ]
    library.SetFilePointer.restype = wintypes.DWORD
    library.CloseHandle.argtypes = [wintypes.HANDLE]
    library.CloseHandle.restype = wintypes.BOOL
    return library


def _ntdll():
    library = ctypes.WinDLL("ntdll")
    library.NtCreateFile.argtypes = [
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        ctypes.POINTER(_ObjectAttributes),
        ctypes.POINTER(_IoStatus),
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    library.NtCreateFile.restype = ctypes.c_ulong
    return library


_KERNEL = _kernel32() if os.name == "nt" else None
_NT = _ntdll() if os.name == "nt" else None


def _kernel() -> Any:
    if _KERNEL is None:
        raise FilesystemRejected("handle_api_unavailable")
    return _KERNEL


def _nt() -> Any:
    if _NT is None:
        raise FilesystemRejected("handle_api_unavailable")
    return _NT


def _file_id(handle: int) -> tuple[int, int, int]:
    info = _ByHandle()
    if not _kernel().GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise FilesystemRejected("handle_identity_unavailable")
    if info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
        raise FilesystemRejected("symlink_or_reparse")
    return (info.dwVolumeSerialNumber, info.nFileIndexHigh, info.nFileIndexLow)


def _reject_name(name: str) -> None:
    if name != Path(name).name or name in {"", ".", ".."}:
        raise FilesystemRejected("path_traversal")
    if any(token in name for token in ("/", "\\", ":")):
        raise FilesystemRejected("path_traversal")
    if name.endswith((" ", ".")):
        raise FilesystemRejected("trailing_dot_or_space")
    if any(ord(char) < 32 for char in name):
        raise FilesystemRejected("control_character")
    if name.split(".", 1)[0].casefold() in _RESERVED_DEVICES:
        raise FilesystemRejected("reserved_device_name")


def _require_same_volume(parent: tuple[int, int, int], child: tuple[int, int, int]) -> None:
    if parent[0] != child[0]:
        raise FilesystemRejected("unexpected_volume")


def _nt_create(root: int, name: str, *, directory: bool) -> int:
    _reject_name(name)
    text = name
    unicode = _UnicodeString(len(text) * 2, len(text) * 2, text)
    attributes = _ObjectAttributes()
    attributes.Length = ctypes.sizeof(_ObjectAttributes)
    attributes.RootDirectory = root
    attributes.ObjectName = ctypes.pointer(unicode)
    attributes.Attributes = 0
    status_block = _IoStatus()
    handle = wintypes.HANDLE()
    if directory:
        access = FILE_LIST_DIRECTORY | FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE
        options = FILE_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT
    else:
        access = FILE_READ_DATA | FILE_WRITE_DATA | FILE_READ_ATTRIBUTES | SYNCHRONIZE
        options = FILE_NON_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT
    status = _nt().NtCreateFile(
        ctypes.byref(handle),
        access,
        ctypes.byref(attributes),
        ctypes.byref(status_block),
        None,
        FILE_ATTRIBUTE_NORMAL,
        FILE_SHARE_ALL,
        FILE_CREATE,
        options,
        None,
        0,
    )
    if status != 0 or not handle.value:
        if status == 0xC0000035:
            raise FilesystemRejected("unsafe_file_replacement" if not directory else "destination_exists")
        raise FilesystemRejected("handle_create_failed")
    return int(handle.value)


class DirectoryHandle:
    """A directory object opened once. Later creates do not reuse its path."""

    def __init__(self, handle: int, identity: tuple[int, int, int]) -> None:
        self.handle = handle
        self.identity = identity
        self.names: list[str] = []
        self.closed = False

    def close(self) -> None:
        if not self.closed:
            _kernel().CloseHandle(self.handle)
            self.closed = True

    def _require_current(self) -> None:
        if self.closed:
            raise FilesystemRejected("handle_closed")
        current = _file_id(self.handle)
        if current != self.identity:
            raise FilesystemRejected("handle_identity_changed")

    def create_directory(self, name: str) -> DirectoryHandle:
        self._require_current()
        self._reject_collision(name)
        handle = _nt_create(self.handle, name, directory=True)
        try:
            identity = _file_id(handle)
            _require_same_volume(self.identity, identity)
        except FilesystemRejected:
            _kernel().CloseHandle(handle)
            raise
        self.names.append(name)
        return DirectoryHandle(handle, identity)

    def write_exclusive(self, name: str, data: bytes) -> int:
        self._require_current()
        self._reject_collision(name)
        handle = _nt_create(self.handle, name, directory=False)
        try:
            info = _ByHandle()
            if not _kernel().GetFileInformationByHandle(handle, ctypes.byref(info)):
                raise FilesystemRejected("handle_identity_unavailable")
            if info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
                raise FilesystemRejected("symlink_or_reparse")
            if info.dwVolumeSerialNumber != self.identity[0]:
                raise FilesystemRejected("unexpected_volume")
            if info.nNumberOfLinks > 1:
                raise FilesystemRejected("hard_link")
            written = wintypes.DWORD(0)
            buffer = ctypes.create_string_buffer(data)
            ok = _kernel().WriteFile(handle, buffer, len(data), ctypes.byref(written), None)
            if not ok or written.value != len(data):
                raise FilesystemRejected("interrupted_write")
            high = ctypes.c_long(0)
            _kernel().SetFilePointer(handle, 0, ctypes.byref(high), 0)
            target = ctypes.create_string_buffer(len(data))
            read = wintypes.DWORD(0)
            ok = _kernel().ReadFile(handle, target, len(data), ctypes.byref(read), None)
            if not ok or read.value != len(data) or target.raw != data:
                raise FilesystemRejected("partial_download")
        except FilesystemRejected:
            _kernel().CloseHandle(handle)
            raise
        self.names.append(name)
        return handle

    def read_existing(self, handle: int, size: int) -> bytes:
        high = ctypes.c_long(0)
        _kernel().SetFilePointer(handle, 0, ctypes.byref(high), 0)
        target = ctypes.create_string_buffer(size)
        read = wintypes.DWORD(0)
        ok = _kernel().ReadFile(handle, target, size, ctypes.byref(read), None)
        if not ok or read.value != size:
            raise FilesystemRejected("partial_download")
        return target.raw

    def _reject_collision(self, name: str) -> None:
        _reject_name(name)
        for existing in self.names:
            if existing.casefold() == name.casefold() and existing != name:
                raise FilesystemRejected("case_collision")


def open_directory(path: Path) -> DirectoryHandle:
    """Open one existing directory without following a reparse point."""
    if os.name != "nt" or _KERNEL is None or _NT is None:
        raise FilesystemRejected("handle_api_unavailable")
    handle = _kernel().CreateFileW(
        str(path),
        FILE_LIST_DIRECTORY | FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
        FILE_SHARE_ALL,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle == INVALID_HANDLE or handle is None or int(handle) == INVALID_HANDLE:
        raise FilesystemRejected("parent_open_failed")
    try:
        identity = _file_id(int(handle))
    except FilesystemRejected:
        _kernel().CloseHandle(handle)
        raise
    return DirectoryHandle(int(handle), identity)
