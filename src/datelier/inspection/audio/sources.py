"""Worker-only audio reference resolution and file/array header inspection."""

import numpy as np
import soundfile as sf

from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.audio.types import (
    AudioLocator,
    AudioMetadata,
    AudioOrigin,
    validate_sample_rate,
)
from datelier.inspection.references.index import ReferenceIndex, resolve
from datelier.inspection.references.types import AssetIdentity, ReferenceSettings
from datelier.io.arrays import ArrayStore


def check_asset(asset: AssetIdentity) -> None:
    stat = asset.path.stat()
    if (stat.st_size, stat.st_mtime_ns) != (asset.size, asset.modified_ns):
        raise ValueError("Audio asset changed; reload the record")


def locate_audio(
    dataset: Dataset,
    file_id: str,
    view_name: str,
    column: str,
    position: int,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    catalog: ArrayCatalog | None = None,
    mapping: ArrayRecordMapping | None = None,
) -> AudioLocator:
    if not 0 <= position < dataset.table.height:
        raise ValueError("Audio table row is outside the current view")
    origin = AudioOrigin(
        file_id, view_name, dataset.revision, int(dataset.row_ids[position]), column
    )
    if catalog is not None and mapping is not None:
        if mapping.layout != ArrayLayout.AUDIO:
            raise ValueError("Confirm a waveform record mapping")
        if not 0 <= origin.row_id < mapping.record_count(catalog):
            raise ValueError("Audio source index is outside the mapped array")
        return AudioLocator(
            origin, catalog=catalog, mapping=mapping, source_index=origin.row_id
        )
    value = dataset.table.get_column(column)[position]
    if not isinstance(value, str) or not value:
        raise ValueError("Audio reference requires a nonempty path or mapped value")
    resolved = resolve(dataset.source.path, column, value, references, index)
    if resolved.asset is None:
        raise ValueError(resolved.message or "Choose an explicit audio mapping")
    return AudioLocator(origin, asset=resolved.asset)


def audio_metadata(
    locator: AudioLocator, array_sample_rate: int | None = None
) -> AudioMetadata:
    validate_sample_rate(array_sample_rate)
    if locator.asset is not None:
        check_asset(locator.asset)
        try:
            info = sf.info(locator.asset.path)
        except (OSError, RuntimeError) as error:
            raise ValueError(
                f"Cannot decode audio header: {error}. "
                "Use a supported WAV, FLAC, OGG or MP3 source."
            ) from error
        result = AudioMetadata(
            int(info.frames),
            int(info.channels),
            int(info.samplerate),
            np.dtype("float64"),
            str(info.format),
            str(info.subtype),
            "full-scale amplitude",
            f"{info.format}/{info.subtype}; original {info.samplerate} Hz; "
            "decoded float64 amplitude; no resampling",
        )
        check_asset(locator.asset)
        if result.channels < 1 or not result.sample_rate:
            raise ValueError("Audio header has an invalid channel count or sample rate")
        return result
    catalog, mapping = locator.catalog, locator.mapping
    if catalog is None or mapping is None or locator.source_index is None:
        raise ValueError("Audio record mapping is unavailable")
    ArrayStore.check_source(catalog)
    count = mapping.record_count(catalog)
    if mapping.layout != ArrayLayout.AUDIO or not 0 <= locator.source_index < count:
        raise ValueError("Confirm a waveform mapping with a valid source index")
    member = catalog.member(mapping.member)
    if member.dtype is None or member.dtype.kind not in "iuf":
        raise ValueError("Audio arrays require real numeric sample values")
    channels = (
        member.shape[mapping.channel_axis] if mapping.channel_axis is not None else 1
    )
    if channels < 1:
        raise ValueError("Audio array has an empty channel dimension")
    return AudioMetadata(
        member.shape[mapping.display_axes[0]],
        channels,
        array_sample_rate,
        member.dtype,
        "Array",
        member.dtype.str,
        "array amplitude" if member.dtype.kind == "f" else "array units",
        f"{mapping.member}; original {member.dtype} samples; "
        + (
            f"configured {array_sample_rate} Hz; no resampling"
            if array_sample_rate is not None
            else "sample rate unknown; configure before signal inspection"
        ),
    )


def prepare_metadata(
    dataset: Dataset,
    file_id: str,
    view_name: str,
    column: str,
    position: int,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    catalog: ArrayCatalog | None = None,
    mapping: ArrayRecordMapping | None = None,
    array_sample_rate: int | None = None,
) -> tuple[AudioLocator, AudioMetadata]:
    locator = locate_audio(
        dataset,
        file_id,
        view_name,
        column,
        position,
        references,
        index,
        catalog,
        mapping,
    )
    return locator, audio_metadata(locator, array_sample_rate)
