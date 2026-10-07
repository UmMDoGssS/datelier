"""Worker-only signal blocks; leases and decoder handles cannot escape a command."""

from collections.abc import Callable, Iterator
from concurrent.futures import CancelledError
from contextlib import contextmanager
from typing import cast

import numpy as np
import soundfile as sf
from numpy.typing import NDArray

from datelier.inspection.audio.sources import audio_metadata, check_asset
from datelier.inspection.audio.types import (
    AudioBlock,
    AudioLocator,
    AudioMetadata,
    AudioRange,
    PreparedAudio,
)
from datelier.io.arrays.storage import ArrayStore

BLOCK_FRAMES = 65536
BLOCK_BYTES = 1024 * 1024
WHOLE_SIGNAL = AudioRange()


def check_stopped(stopped: Callable[[], bool] | None) -> None:
    if stopped is not None and stopped():
        raise CancelledError("Audio preparation abandoned")


@contextmanager
def audio_blocks(
    locator: AudioLocator,
    metadata: AudioMetadata,
    arrays: ArrayStore,
    selected: AudioRange = WHOLE_SIGNAL,
    *,
    block_frames: int = BLOCK_FRAMES,
    block_bytes: int = BLOCK_BYTES,
    stopped: Callable[[], bool] | None = None,
) -> Iterator[Iterator[AudioBlock]]:
    """Read original decoded/file or raw/array values without rate conversion.

    Each block is an owned copy. Consumers may retain a visible block after its
    array lease closes; they must not retain the collection of all blocks.
    """
    check_stopped(stopped)
    if block_frames < 1 or block_bytes < 1:
        raise ValueError("Audio block budgets must be positive")
    start, stop = selected.bounds(metadata.frames)
    size = metadata.channels * metadata.dtype.itemsize
    if size > block_bytes:
        raise ValueError("Audio block budget cannot hold one complete sample frame")
    count = min(block_frames, block_bytes // size)
    current = audio_metadata(locator, metadata.sample_rate if locator.catalog else None)
    if current != metadata:
        raise ValueError("Audio metadata changed; reload the record")
    if locator.asset is not None:
        try:
            with sf.SoundFile(locator.asset.path) as stream:
                stream.seek(start)

                def file_blocks() -> Iterator[AudioBlock]:
                    for offset in range(start, stop, count):
                        check_stopped(stopped)
                        assert locator.asset is not None
                        check_asset(locator.asset)
                        raw = cast(
                            NDArray[np.generic],
                            stream.read(
                                min(count, stop - offset),
                                dtype="float64",
                                always_2d=True,
                            ),
                        )
                        if raw.shape != (min(count, stop - offset), metadata.channels):
                            raise ValueError(
                                "Audio decoded fewer frames than its header"
                            )
                        raw.flags.writeable = False
                        yield AudioBlock(offset, raw)

                yield file_blocks()
            check_asset(locator.asset)
        except (OSError, RuntimeError) as error:
            raise ValueError(f"Cannot read audio samples: {error}") from error
    else:
        catalog, mapping = locator.catalog, locator.mapping
        if catalog is None or mapping is None or locator.source_index is None:
            raise ValueError("Audio record mapping is unavailable")
        shape = catalog.member(mapping.member).shape
        selectors: list[int | slice] = list(mapping.fixed or (0,) * len(shape))
        selectors[mapping.record_axis] = locator.source_index
        sample_axis = mapping.display_axes[0]
        axes = (sample_axis,)
        if mapping.channel_axis is not None:
            selectors[mapping.channel_axis] = slice(None)
            axes = (sample_axis, mapping.channel_axis)
        with arrays.open_member(catalog, mapping.member, stopped) as array:

            def array_blocks() -> Iterator[AudioBlock]:
                for offset in range(start, stop, count):
                    check_stopped(stopped)
                    ArrayStore.check_source(catalog)
                    selectors[sample_axis] = slice(offset, min(offset + count, stop))
                    raw = np.asarray(array[tuple(selectors)])
                    if len(axes) == 2:
                        raw = raw.transpose(
                            tuple(sorted(axes).index(axis) for axis in axes)
                        )
                    else:
                        raw = raw[:, None]
                    owned = cast(NDArray[np.generic], raw.copy())
                    owned.flags.writeable = False
                    yield AudioBlock(offset, owned)

            yield array_blocks()
    check_stopped(stopped)


def prepare_window(
    locator: AudioLocator,
    metadata: AudioMetadata,
    selected: AudioRange,
    arrays: ArrayStore,
    cpu_bytes: int = 16 * 1024 * 1024,
    stopped: Callable[[], bool] | None = None,
) -> PreparedAudio:
    start, stop = selected.bounds(metadata.frames)
    size = (stop - start) * metadata.channels * metadata.dtype.itemsize
    if cpu_bytes < 1 or size > cpu_bytes:
        raise ValueError(
            "Sample window exceeds CPU budget; choose a smaller time range"
        )
    raw = cast(
        NDArray[np.generic],
        np.empty((stop - start, metadata.channels), dtype=metadata.dtype),
    )
    with audio_blocks(locator, metadata, arrays, selected, stopped=stopped) as blocks:
        for block in blocks:
            offset = block.start - start
            raw[offset : offset + len(block.samples)] = block.samples
    raw.flags.writeable = False
    return PreparedAudio(locator, metadata, AudioRange(start, stop), raw)
