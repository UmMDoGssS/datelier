"""Original-frame ring playback, bounded callback behavior and explicit PCM units."""

from dataclasses import replace
from pathlib import Path
from time import perf_counter

import numpy as np
import pytest
import soundfile as sf

from datelier.inspection.audio.decoding import prepare_metadata
from datelier.inspection.audio.playback.buffer import PlaybackRing
from datelier.inspection.audio.playback.conversion import output_samples
from datelier.inspection.audio.playback.types import PlaybackRequest, RenderAction
from datelier.inspection.audio.types import AudioRange
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.media import load_media


@pytest.mark.parametrize(
    "dtype", ["int16", "int32", "int64", "uint8", "uint16", "uint64"]
)
def test_integer_pcm_mapping_preserves_original_values_and_midpoint(
    dtype: str,
) -> None:
    bounds = np.iinfo(dtype)
    midpoint = 0 if bounds.min < 0 else (int(bounds.max) + 1) // 2
    raw = np.array([[bounds.min], [midpoint], [bounds.max]], dtype=dtype)
    before = raw.copy()
    converted = output_samples(raw)
    assert converted.values[0, 0] == -1 and converted.values[1, 0] == 0
    assert converted.values[2, 0] == pytest.approx(
        (bounds.max - midpoint) / 2 ** (raw.dtype.itemsize * 8 - 1)
    )
    np.testing.assert_equal(raw, before)
    assert not converted.values.flags.writeable and converted.nonfinite == 0


def test_float_conversion_zeroes_only_nonfinite_and_defers_volume_clipping() -> None:
    raw = np.array([[2, -2], [np.nan, np.inf], [1e300, -1e300]])
    original = raw.copy()
    samples = output_samples(raw)
    assert samples.nonfinite == 2
    assert samples.values[0, 0] == 2 and samples.values[2, 0] == 1e300
    ring = PlaybackRing(4, 2, 700, block_frames=2)
    assert ring.append(700, samples.values)
    ring.finish()
    output = np.empty((4, 2), dtype=np.float32)
    assert ring.render(output, 0.25, paused=False, stopped=False) == RenderAction.FINISH
    np.testing.assert_equal(output, [[0.5, -0.5], [0, 0], [1, -1], [0, 0]])
    assert ring.position == 703  # Padding is not a source sample frame.
    np.testing.assert_equal(raw, original)


def test_ring_wrap_backpressure_pause_mute_and_end_padding() -> None:
    ring = PlaybackRing(8, 1, 100, block_frames=4)
    assert ring.append(100, np.arange(4, dtype=np.float64)[:, None])
    out = np.empty((3, 1), dtype=np.float32)
    assert ring.render(out, 0.1, paused=True, stopped=False) == RenderAction.CONTINUE
    assert ring.position == 100 and not out.any()
    ring.render(out, 0.1, paused=False, stopped=False)
    np.testing.assert_allclose(out[:, 0], [0, 0.1, 0.2])
    assert not ring.append(104, np.zeros((8, 1)))
    assert ring.append(104, np.arange(4, 9, dtype=np.float64)[:, None])
    ring.finish()
    out = np.empty((8, 1), dtype=np.float32)
    assert ring.render(out, 0.1, paused=False, stopped=False) == RenderAction.FINISH
    np.testing.assert_allclose(out[:, 0], [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0, 0])
    assert ring.position == 109 and ring.underruns == 0
    with pytest.raises(ValueError, match="contiguous"):
        ring.append(109, np.zeros((1, 1)))
    other = PlaybackRing(4, 1, 42)
    other.append(42, np.ones((4, 1)))
    other.render(out, 0, paused=False, stopped=False)
    assert not out.any() and other.position == 46


def test_busy_or_empty_ring_never_waits_and_stop_discards_output() -> None:
    ring = PlaybackRing(4, 1, 50)
    ring.append(50, np.ones((4, 1)))
    out = np.ones((4, 1), dtype=np.float32)
    with ring.lock:
        started = perf_counter()
        assert ring.render(out, 1, paused=False, stopped=False) == RenderAction.CONTINUE
        assert perf_counter() - started < 0.1
    assert not out.any() and ring.position == 50 and ring.underruns == 1
    assert ring.render(out, 1, paused=False, stopped=True) == RenderAction.ABORT
    assert not out.any() and ring.position == 50
    empty = PlaybackRing(4, 1, 90)
    assert empty.render(out, 1, paused=False, stopped=False) == RenderAction.CONTINUE
    assert not out.any() and empty.position == 90 and empty.underruns == 1


def test_request_budgets_include_all_channels_and_require_known_rate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "signal.wav"
    sf.write(path, np.zeros((1000, 2)), 8000)
    locator, metadata = prepare_metadata(
        load_media(path).dataset, "file", "view", "path", 0, ReferenceSettings(), None
    )
    request = PlaybackRequest(locator, metadata, AudioRange(100, 900), start_frame=300)
    ring = PlaybackRing.for_request(request)
    assert ring.position == 300 and ring.retained_bytes <= request.cpu_bytes
    assert ring.samples.shape[1] == 2
    selected = replace(request, channel=1)
    assert PlaybackRing.for_request(selected).samples.shape[1] == 1
    wide = replace(request, metadata=replace(metadata, channels=262145))
    with pytest.raises(ValueError, match="budget"):
        PlaybackRing.for_request(wide)
    assert (
        PlaybackRing.for_request(replace(wide, channel=262144)).retained_bytes
        <= wide.cpu_bytes
    )
    for invalid in (
        replace(request, metadata=replace(metadata, sample_rate=None)),
        replace(request, range=AudioRange(100, 100)),
        replace(request, start_frame=50),
        replace(request, channel=2),
    ):
        with pytest.raises(ValueError):
            invalid.validate()


def test_unrepresentable_float_and_complex_playback_have_diagnostics() -> None:
    with pytest.raises(ValueError, match="Float64"):
        output_samples(np.array([[np.finfo(np.longdouble).max]], dtype=np.longdouble))
    with pytest.raises(ValueError, match="real"):
        output_samples(np.array([[1 + 2j]]))
