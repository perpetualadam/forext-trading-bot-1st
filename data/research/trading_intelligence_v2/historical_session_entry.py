"""Run from the repository root. No arguments, credential values or permit files."""
import importlib.util
from pathlib import Path
import sys


def launch(argv=None):
    package=Path(__file__).resolve().parent
    if 'tiv2' not in sys.modules:
        spec=importlib.util.spec_from_file_location('tiv2',package/'__init__.py',submodule_search_locations=[str(package)])
        module=importlib.util.module_from_spec(spec);sys.modules['tiv2']=module;spec.loader.exec_module(module)
    from tiv2.direct_history import launch as entry
    return entry(argv)


if __name__=='__main__':raise SystemExit(launch())
