"""Worker-only explicit collection headers or exact streaming signal statistics."""

from contextlib import ExitStack
from threading import Event

import polars as pl

from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.audio.collections.records import (
    CHANNEL_SCHEMA,
    RECORD_SCHEMA,
    channel_rows,
    fraction,
)
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
    AudioScopeMode,
)
from datelier.inspection.audio.collections.types import (
    AudioCollectionProfile,
    CollectionProgress,
)
from datelier.inspection.audio.reading import check_stopped
from datelier.inspection.audio.sources import check_asset, prepare_metadata
from datelier.inspection.audio.statistics import profile_signal
from datelier.inspection.audio.types import AudioLocator, AudioRange
from datelier.inspection.records.prepare import prepare_records
from datelier.inspection.records.types import InspectSettings, RecordMode
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.arrays.storage import ArrayStore


def audio_positions(
    dataset: Dataset, settings: AudioCollectionSettings, selection: tuple[int, ...]
) -> pl.Series:
    scope = settings.scope
    scope.validate()
    if scope.mode == AudioScopeMode.COLLECTION:
        return pl.int_range(0, dataset.table.height, eager=True)
    return prepare_records(
        dataset,
        InspectSettings(
            RecordMode(scope.mode.value), scope.start, scope.count, scope.seed
        ),
        selection,
    ).positions


def validate_input(
    dataset: Dataset,
    settings: AudioCollectionSettings,
    catalog: ArrayCatalog | None,
    mapping: ArrayRecordMapping | None,
) -> None:
    settings.validate()
    if settings.column is None:
        raise ValueError("Choose an audio field or confirmed waveform mapping")
    if mapping is not None:
        if (
            catalog is None
            or mapping.layout != ArrayLayout.AUDIO
            or settings.column != mapping.member
        ):
            raise ValueError("Choose the current confirmed waveform member")
        mapping.record_count(catalog)
        if (
            settings.mode == AudioProfileMode.SIGNAL
            and settings.array_sample_rate is None
        ):
            raise ValueError(
                "Configure the array sample rate before exact signal statistics"
            )
    elif dataset.table.schema.get(settings.column) != pl.String:
        raise ValueError("Audio references require a physical String field")


def check_locators(locators: tuple[AudioLocator, ...], stop: Event) -> None:
    for locator in locators:
        check_stopped(stop.is_set)
        if locator.asset is not None:
            check_asset(locator.asset)
        elif locator.catalog is not None:
            ArrayStore.check_source(locator.catalog)


def scan_collection(
    dataset: Dataset,
    file_id: str,
    view_name: str,
    settings: AudioCollectionSettings,
    selection: tuple[int, ...],
    references: ReferenceSettings,
    index: ReferenceIndex | None,
    arrays: ArrayStore,
    stop: Event,
    progress: CollectionProgress,
    catalog: ArrayCatalog | None = None,
    mapping: ArrayRecordMapping | None = None,
) -> tuple[AudioCollectionProfile, tuple[AudioLocator, ...]]:
    validate_input(dataset, settings, catalog, mapping)
    assert settings.column is not None
    positions = audio_positions(dataset, settings, selection)
    records: list[tuple[object, ...]] = []
    channels: list[tuple[object, ...]] = []
    locators: list[AudioLocator] = []
    values = dataset.table[settings.column] if mapping is None else None
    row_ids = dataset.row_ids
    with ExitStack() as leases:
        if (
            catalog is not None
            and mapping is not None
            and len(positions)
            and settings.mode == AudioProfileMode.SIGNAL
        ):
            leases.enter_context(
                arrays.open_member(catalog, mapping.member, stop.is_set)
            )
        for number, position in enumerate(positions):
            check_stopped(stop.is_set)
            row_id = int(row_ids[position])
            reference = (
                str(values[position])
                if values is not None and values[position] is not None
                else None
            )
            progress.update(
                f"{dataset.source.path.name} {view_name}: {settings.mode}",
                number,
                len(positions),
            )
            prefix = (row_id, int(position), reference)
            if values is not None and values[position] is None:
                records.append(
                    (*prefix, "Null", "Audio reference is null", *((None,) * 7))
                )
                continue
            try:
                locator, metadata = prepare_metadata(
                    dataset,
                    file_id,
                    view_name,
                    settings.column,
                    int(position),
                    references,
                    index,
                    catalog,
                    mapping,
                    settings.array_sample_rate,
                )
                signal = None
                if settings.mode == AudioProfileMode.SIGNAL:
                    signal = profile_signal(
                        locator,
                        metadata,
                        AudioRange(),
                        settings.thresholds,
                        arrays,
                        stop.is_set,
                    )
                prepared_channels = channel_rows(signal) if signal is not None else []
                check_stopped(stop.is_set)
                records.append(
                    (
                        *prefix,
                        "Ready",
                        "",
                        metadata.frames,
                        metadata.channels,
                        metadata.sample_rate,
                        metadata.duration,
                        fraction(signal.silent_frames, signal.frames)
                        if signal
                        else None,
                        signal.longest_silence_frames / metadata.require_rate()
                        if signal
                        else None,
                        fraction(signal.nonfinite_frames, signal.frames)
                        if signal
                        else None,
                    )
                )
                channels.extend(prepared_channels)
                locators.append(locator)
            except Exception as error:
                check_stopped(stop.is_set)
                records.append((*prefix, "Failed", str(error), *((None,) * 7)))
            if number % 32 == 31:
                stop.wait(0.001)
        check_locators(tuple(locators), stop)
    progress.update("Audio collection ready", len(positions), len(positions))
    return AudioCollectionProfile(
        file_id,
        view_name,
        dataset.revision,
        dataset.source,
        settings,
        mapping,
        dataset.table.height,
        pl.DataFrame(records, schema=RECORD_SCHEMA, orient="row"),
        pl.DataFrame(channels, schema=CHANNEL_SCHEMA, orient="row"),
        sum(row[3] == "Ready" for row in records),
        sum(row[3] == "Null" for row in records),
        sum(row[3] == "Failed" for row in records),
    ), tuple(locators)
