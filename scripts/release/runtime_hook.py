"""Resolve bundled PortAudio before sounddevice's lazy Linux discovery.

sounddevice calls ctypes.util.find_library before loading its CFFI boundary.
On Linux that search normally consults the host linker cache, which need not
contain our bundled library. All other library discovery stays unchanged.
"""

import ctypes.util
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
