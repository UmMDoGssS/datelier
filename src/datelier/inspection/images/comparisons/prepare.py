"""Two source-checked passes with common physical bins across scoped sources."""

from contextlib import ExitStack
from dataclasses import replace
from threading import Event

from datelier.inspection.images.comparisons.settings import ImageComparisonSettings
from datelier.inspection.images.comparisons.types import (
    ImageComparisonCurve,
    ImageComparisonInput,
    PreparedImageComparison,
)
from datelier.inspection.images.pixels import check_cancelled
from datelier.inspection.images.profile_histograms import dimension_histograms
from datelier.inspection.images.profile_scan import (
    ImageProfileScan,
    scan_image_profile,
    validate_profile_input,
)
from datelier.inspection.images.profile_types import (
    ChannelKey,
    ChannelSummary,
    ImageHistogram,
    ImageProgress,
)
from datelier.inspection.images.profiles import finish_image_profile, image_positions
from datelier.inspection.images.sources import check_asset
from datelier.inspection.images.storage import ImageStore
from datelier.io.arrays import ArrayStore


def include_bounds(
    bounds: dict[ChannelKey, tuple[int | float, int | float]], summary: ChannelSummary
) -> None:
    if summary.minimum is None or summary.maximum is None:
        return
    lo, hi = bounds.get(summary.key, (summary.minimum, summary.maximum))
    bounds[summary.key] = min(lo, summary.minimum), max(hi, summary.maximum)


def proportions(chart: ImageHistogram | None) -> ImageHistogram | None:
    if chart is None:
        return None
    total = float(chart.counts.sum())
    if not total:
        return chart
    return replace(
        chart,
        counts=chart.counts / total,
        plot_counts=chart.plot_counts / total
        if chart.plot_counts is not None
        else None,
    )


def prepare_comparison(
    inputs: tuple[ImageComparisonInput, ...],
    recipe: ImageComparisonSettings,
    stop: Event,
    progress: ImageProgress,
) -> PreparedImageComparison:
    recipe.validate()
    if len(inputs) < 2 or tuple(item.source for item in inputs) != recipe.sources:
        raise ValueError("Map two available image sources; recover missing files first")
    images = ImageStore(retained_bytes=0)
    owned: list[ArrayStore] = []
    scans: list[tuple[ImageProfileScan, ArrayStore]] = []
    bounds: dict[ChannelKey, tuple[int | float, int | float]] = {}
    try:
        with ExitStack() as leases:
            for item in inputs:
                check_cancelled(stop)
                settings = replace(item.source.profile, bins=recipe.bins)
                validate_profile_input(
                    item.dataset, settings, item.catalog, item.mapping
                )
                positions = image_positions(item.dataset, settings, item.selection)
                arrays = item.arrays
                if arrays is None:
                    arrays = ArrayStore(retained_bytes=0)
                    owned.append(arrays)
                if (
                    item.catalog is not None
                    and item.mapping is not None
                    and len(positions)
                ):
                    leases.enter_context(
                        arrays.open_member(
                            item.catalog, item.mapping.member, stop.is_set
                        )
                    )
                scan = scan_image_profile(
                    item.dataset,
                    item.source.file_id,
                    item.view_name,
                    settings,
                    positions,
                    item.references,
                    item.index,
                    images,
                    arrays,
                    stop,
                    progress,
                    item.catalog,
                    item.mapping,
                )
                scans.append((scan, arrays))
                for key, moments in scan.pooled.items():
                    include_bounds(bounds, moments.summary(key))
                for summary in dimension_histograms(scan.records, recipe.bins)[1]:
                    include_bounds(bounds, summary)
            profiles = tuple(
                finish_image_profile(scan, images, arrays, stop, progress, bounds)
                for scan, arrays in scans
            )
            # Recheck earlier contributors after all later sources finish.
            for scan, _ in scans:
                for record in scan.successful:
                    check_cancelled(stop)
                    if record.locator.asset is not None:
                        check_asset(record.locator.asset)
                    elif record.locator.catalog is not None:
                        ArrayStore.check_source(record.locator.catalog)
            keys: dict[ChannelKey, list[ImageHistogram | None]] = {}
            for number, profile in enumerate(profiles):
                for summary, chart in zip(
                    (*profile.dimension_summaries, *profile.summaries),
                    (*profile.dimensions, *profile.channels),
                    strict=True,
                ):
                    empty: list[ImageHistogram | None] = [None] * len(profiles)
                    keys.setdefault(summary.key, empty)[number] = chart
            curves = tuple(
                ImageComparisonCurve(
                    key, tuple(charts), tuple(proportions(chart) for chart in charts)
                )
                for key, charts in keys.items()
            )
            check_cancelled(stop)
            progress.update("Image comparison ready", len(inputs), len(inputs))
            return PreparedImageComparison(
                recipe, tuple(item.label for item in inputs), profiles, bounds, curves
            )
    finally:
        images.cleanup()
        for arrays in owned:
            arrays.close()
