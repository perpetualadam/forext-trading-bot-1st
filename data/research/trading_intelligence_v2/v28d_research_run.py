"""Fixed offline research tests under the existing loopback/OS audit barrier."""
import importlib.util,sys
from pathlib import Path
p=Path(__file__).resolve().parent
# Reuse the existing runner and its barriers, without editing acquisition entrypoints.
s=importlib.util.spec_from_file_location('_runner',p/'v26d_run.py')
# A fixed in-process selector is added by v26d_run; never accepts arbitrary modules.
sys.argv=[str(p/'v26d_run.py'),'--v28d-research-tests']
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
