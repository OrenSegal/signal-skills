"""Load a plugin module by file path under a unique name.

Several plugins each ship their own ledger.py/resolve.py with the same
module name but different (deliberately non-shared) logic, so a plain
`import ledger` would collide. Load each one explicitly by path instead.
"""
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load(plugin, filename):
    path = REPO_ROOT / "plugins" / plugin / filename
    mod_name = f"_ss_{plugin.replace('-', '_')}_{filename[:-3]}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module
