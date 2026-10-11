"""Explicit source-checked collection comparisons, with one bounded scan at a time."""

from threading import Event

from datelier.inspection.audio.collections.scan import check_locators, scan_collection
from datelier.inspection.audio.collections.types import CollectionProgress
from datelier.inspection.audio.comparisons.distributions import metrics, prepare_curve
from datelier.inspection.audio.comparisons.settings import AudioComparisonSettings
from datelier.inspection.audio.comparisons.types import (
    AudioComparisonInput,
    PreparedAudioComparison,
)
from datelier.inspection.audio.reading import check_stopped
from datelier.io.arrays import ArrayStore


def prepare_comparison(
    inputs: tuple[AudioComparisonInput, ...],
    recipe: AudioComparisonSettings,
    stop: Event,
    progress: CollectionProgress,
) -> PreparedAudioComparison:
    recipe.validate()
    if len(inputs) < 2 or tuple(i.source for i in inputs) != recipe.sources:
        raise ValueError("Map two available audio sources; recover missing files first")
    profiles, locators = [], []
    for item in inputs:
        check_stopped(stop.is_set)
        owned = item.arrays is None
        arrays = (
            item.arrays if item.arrays is not None else ArrayStore(retained_bytes=0)
        )
        try:
            profile, used = scan_collection(
                item.dataset,
                item.source.file_id,
                item.view_name,
                item.source.profile,
                item.selection,
                item.references,
                item.index,
                arrays,
                stop,
                progress,
                item.catalog,
                item.mapping,
            )
            profiles.append(profile)
            locators.extend(used)
        finally:
            if owned:
                arrays.close()
    check_locators(tuple(locators), stop)
    curves = []
    for metric in metrics(tuple(profiles)):
        check_stopped(stop.is_set)
        curves.append(prepare_curve(tuple(profiles), metric, recipe.bins))
    check_locators(tuple(locators), stop)
    progress.update("Audio comparison ready", len(inputs), len(inputs))
    return PreparedAudioComparison(
        recipe, tuple(i.label for i in inputs), tuple(profiles), tuple(curves)
    )
