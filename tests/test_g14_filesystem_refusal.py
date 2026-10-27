"""The Windows-only filesystem helper must fail closed without native APIs."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("missing", ["_KERNEL", "_NT"])
def test_absent_native_api_cannot_open_or_modify_destination(tmp_path, monkeypatch, missing):
    spec = importlib.util.spec_from_file_location(
        "g14_filesystem_refusal", Path(__file__).with_name("g14_7_fs.py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, missing, None)
    marker = tmp_path / "marker.bin"
    marker.write_bytes(b"unchanged")
    with pytest.raises(module.FilesystemRejected, match="handle_api_unavailable"):
        module.open_directory(tmp_path)
    assert marker.read_bytes() == b"unchanged"
    assert list(tmp_path.iterdir()) == [marker]
