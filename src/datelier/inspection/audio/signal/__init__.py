"""Worker-prepared waveform extrema, one-sided PSD, and HTK mel band power.

Views preserve the original rate and selected frame/channel provenance. FFT/hop,
window, frequency bounds, binning, and linear/dB display are explicit. Streaming
preparation bounds retained grids; peak aggregation and trailing-frame omissions
are reported. Mel triangles integrate PSD into original amplitude-squared band
power. Display normalization never alters statistics or source samples.
"""

from datelier.inspection.audio.signal.types import AudioViewKind as AudioViewKind
from datelier.inspection.audio.signal.types import AudioWindow as AudioWindow
from datelier.inspection.audio.signal.types import (
    PreparedSignalView as PreparedSignalView,
)
from datelier.inspection.audio.signal.types import (
    SignalViewSettings as SignalViewSettings,
)
from datelier.inspection.audio.signal.types import SpectralTile as SpectralTile
from datelier.inspection.audio.signal.types import SpectralView as SpectralView
from datelier.inspection.audio.signal.types import SpectrumScale as SpectrumScale
from datelier.inspection.audio.signal.types import WaveformEnvelope as WaveformEnvelope
