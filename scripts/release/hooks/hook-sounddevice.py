"""Collect the explicitly selected Linux PortAudio runtime, including its SONAME."""

import os
from pathlib import Path

library = Path(os.environ["DATELIER_PORTAUDIO_LIBRARY"]).resolve()
binaries = [(str(library), ".")]
