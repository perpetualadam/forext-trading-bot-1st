"""Owned temporary workspace cleanup compatible with the offline audit hooks."""

from contextlib import contextmanager
from pathlib import Path
import os
import secrets
import stat
import tempfile


def _is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _cleanup_owned_tree(root, identity):
    """Use path operations so the existing blanket FD denial stays enforced.

    Never follow links, relax permissions, scan siblings, or ignore failures.
    The private mkdtemp directory belongs to this invocation alone.
    """
    def check_root():
        info = root.lstat()
        if _is_link(info) or not stat.S_ISDIR(info.st_mode):
            raise PermissionError("TIV2_TEMP_LINK_REFUSED")
        if (info.st_dev, info.st_ino) != identity:
            raise PermissionError("TIV2_TEMP_IDENTITY_CHANGED")

    def remove(directory):
        check_root()
        info = directory.lstat()
        if _is_link(info) or not directory.resolve().is_relative_to(root):
            raise PermissionError("TIV2_TEMP_LINK_REFUSED")
        for child in directory.iterdir():
            check_root()
            info = child.lstat()
            if _is_link(info) or not child.resolve().is_relative_to(root):
                raise PermissionError("TIV2_TEMP_LINK_REFUSED")
            if stat.S_ISDIR(info.st_mode):
                remove(child)
            elif stat.S_ISREG(info.st_mode):
                child.unlink()
            else:
                raise PermissionError("TIV2_TEMP_SPECIAL_FILE_REFUSED")
        check_root()
        directory.rmdir()

    remove(root)


@contextmanager
def temporary_workspace():
    if os.name == "nt":
        # Python 3.13's mode=0700 DACL drops restricted-token/sandbox ACEs.
        # Keep the protected per-user OS temp parent's inherited ACL instead;
        # do not grant permissions, reset ACLs, or reuse an existing directory.
        parent = Path(tempfile.gettempdir()).resolve()
        for _ in range(100):
            root = parent / ("tiv2-" + secrets.token_hex(16))
            try:
                root.mkdir()
            except FileExistsError:
                continue
            break
        else:
            raise FileExistsError("TIV2_TEMP_NAME_COLLISIONS")
    else:
        root = Path(tempfile.mkdtemp(prefix="tiv2-")).resolve()
    info = root.lstat()
    identity = (info.st_dev, info.st_ino)
    try:
        yield root
    finally:
        _cleanup_owned_tree(root, identity)
