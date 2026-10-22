"""Frozen library discovery and the catalog's single-worker analysis policy.

sounddevice calls ctypes.util.find_library before loading its CFFI boundary.
On Linux that search normally consults the host linker cache, which need not
contain our bundled library. All other library discovery stays unchanged.
"""

import ctypes.util
import os
import sys
from pathlib import Path

system_find_library = ctypes.util.find_library
bundle_root = getattr(sys, "_MEIPASS", None)
if not isinstance(bundle_root, str):
    raise RuntimeError("The PortAudio runtime hook requires a frozen bundle")
portaudio = Path(bundle_root) / "libportaudio.so.2"


def find_library(name: str) -> str | None:
    if name == "portaudio" and portaudio.is_file():
        return str(portaudio)
    return system_find_library(name)


ctypes.util.find_library = find_library

# Catalog estimators use n_jobs=1. Honor that bound during joblib's physical-core
# discovery too, without requiring an external lscpu executable in the bundle.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
