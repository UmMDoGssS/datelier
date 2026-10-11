"""Fresh-process common-bin comparison resources, leases and source preservation."""

import argparse
import hashlib
import json
import resource
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import perf_counter
from unittest.mock import patch

import numpy as np
import polars as pl
from numpy.typing import NDArray
from PIL import Image

from datelier.core.dataset import Dataset
from datelier.inspection.arrays.mapping import ArrayLayout, ArrayRecordMapping
from datelier.inspection.arrays.types import ArrayCatalog
from datelier.inspection.images.comparisons.prepare import prepare_comparison
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings,
    ImageComparisonSource,
)
from datelier.inspection.images.comparisons.types import ImageComparisonInput
from datelier.inspection.images.profile_types import (
    ImageProfileSettings,
    ImageProgress,
    PixelScope,
)
from datelier.inspection.images.storage import ImageStore
from datelier.inspection.references.types import AssetIdentity
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.media import load_media
from datelier.io.types import MediaOptions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("folder", "array"), default="folder")
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    stores = [ArrayStore(retained_bytes=1024 * 1024) for _ in range(2)]
    temporary: set[Path] = set()
    peak_image_disk = peak_image_files = retained_image = decodes = 0
    peak_array_disk = 0
    image_open, array_open = ImageStore.open_file, ArrayStore.open_member

    @contextmanager
    def measured_image(
        self: ImageStore,
        asset: AssetIdentity,
        stopped: Callable[[], bool] | None = None,
    ) -> Iterator[NDArray[np.generic]]:
        nonlocal peak_image_disk, peak_image_files, retained_image, decodes
        with image_open(self, asset, stopped) as raw:
            if self.temporary_path is not None:
                temporary.add(self.temporary_path)
                peak_image_files = max(
                    peak_image_files, len(list(self.temporary_path.iterdir()))
                )
            peak_image_disk = max(peak_image_disk, self.stored_bytes)
            yield raw
        retained_image = max(retained_image, self.stored_bytes)
        decodes = self.decodes

    @contextmanager
    def measured_array(
        self: ArrayStore,
        catalog: ArrayCatalog,
        name: str,
        stopped: Callable[[], bool] | None = None,
    ) -> Iterator[NDArray[np.generic]]:
        nonlocal peak_array_disk
        with array_open(self, catalog, name, stopped) as raw:
            if self.temporary_path is not None:
                temporary.add(self.temporary_path)
            peak_array_disk = max(
                peak_array_disk, sum(store.stored_bytes for store in stores)
            )
            yield raw

    with TemporaryDirectory(prefix="datelier-image-comparison-bench-") as directory:
        root = Path(directory)
        inputs: list[ImageComparisonInput] = []
        count = 100
        for number, arrays in enumerate(stores):
            folder = root / str(number)
            folder.mkdir()
            catalog = mapping = None
            if args.kind == "folder":
                for index in range(count):
                    Image.new("RGB", (256, 256), (index + number * 50, 20, 30)).save(
                        folder / f"{index:03}.png"
                    )
                (folder / "corrupt.png").write_bytes(b"corrupt")
                members = tuple(f"{index:03}.png" for index in range(count)) + (
                    "corrupt.png",
                    "missing.png",
                )
                dataset = load_media(folder, MediaOptions(manifest=members)).dataset
                column = "path"
            else:
                raw = np.empty((count, 256, 256, 3), dtype=np.uint8)
                for index in range(count):
                    raw[index] = (index + number * 50, 20, 30)
                path = folder / "images.npz"
                np.savez_compressed(path, images=raw, unselected=np.ones((100, 100)))
                del raw
                catalog = inspect_arrays(path)
                dataset = Dataset.from_source(
                    pl.DataFrame({"record_index": range(count)}), catalog.source
                )
                mapping = ArrayRecordMapping(
                    "images",
                    layout=ArrayLayout.IMAGE,
                    display_axes=(1, 2),
                    channel_axis=3,
                )
                column = "images"
            source = ImageComparisonSource(
                str(number),
                ImageProfileSettings(
                    column,
                    pixels=PixelScope.SAMPLE if args.sample else PixelScope.EXACT,
                    pixel_count=1024,
                ),
            )
            inputs.append(
                ImageComparisonInput(
                    source,
                    dataset,
                    str(number),
                    arrays=arrays,
                    catalog=catalog,
                    mapping=mapping,
                )
            )
        paths = tuple(path for path in root.rglob("*") if path.is_file())
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        settings = ImageComparisonSettings(tuple(item.source for item in inputs), 16)
        start = perf_counter()
        with (
            patch.object(ImageStore, "open_file", measured_image),
            patch.object(ArrayStore, "open_member", measured_array),
        ):
            result = prepare_comparison(
                tuple(inputs), settings, Event(), ImageProgress()
            )
        seconds = perf_counter() - start
        retained_arrays = [store.stored_bytes for store in stores]
        for store in stores:
            store.close()
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        for index, profile in enumerate(result.profiles):
            assert profile.ready == count
            assert profile.total_pixels == count * 256 * 256
            assert profile.profiled_pixels == count * (
                1024 if args.sample else 256 * 256
            )
            assert (
                next(
                    summary.mean
                    for summary in profile.summaries
                    if summary.key.name == "R"
                )
                == 49.5 + index * 50
            )
            assert profile.sampled_pixels == args.sample
        red = next(curve for curve in result.curves if curve.key.name == "R")
        first, second = red.counts
        assert first is not None and second is not None
        np.testing.assert_array_equal(first.edges, second.edges)
        assert first.edges[0] == 0 and first.edges[-1] == 149
        assert all(
            chart is not None and abs(float(chart.counts.sum()) - 1) < 1e-12
            for chart in red.proportions
        )
        if args.kind == "folder":
            assert all(
                profile.unresolved == profile.failures == 1
                for profile in result.profiles
            )
            assert (
                peak_image_files == 1 and retained_image == 0 and decodes == 4 * count
            )
        else:
            assert [store.extractions for store in stores] == [1, 1]
            assert retained_arrays == [0, 0]
            assert peak_array_disk == 2 * (count * 256 * 256 * 3 + 128)
        assert seconds < 20, seconds
        assert peak_rss - baseline < 128 * 1024 * 1024
        assert all(not path.exists() for path in temporary)
        assert all(
            hashlib.sha256(path.read_bytes()).hexdigest() == digest
            for path, digest in before.items()
        )
        report = {
            "kind": args.kind,
            "sampled": args.sample,
            "sources": 2,
            "images_per_source": count,
            "dimensions": [256, 256],
            "comparison_seconds": seconds,
            "baseline_rss_bytes": baseline,
            "peak_rss_bytes": peak_rss,
            "rss_increase_bytes": peak_rss - baseline,
            "result_bytes": result.retained_bytes,
            "peak_image_disk_bytes": peak_image_disk,
            "peak_image_files": peak_image_files,
            "retained_image_bytes": retained_image,
            "image_decodes": decodes,
            "peak_array_disk_bytes": peak_array_disk,
            "array_extractions": [store.extractions for store in stores],
            "array_retained_bytes": retained_arrays,
            "profiled_pixels": [profile.profiled_pixels for profile in result.profiles],
            "red_means": [49.5, 99.5],
            "shared_red_bounds": [0, 149],
            "cleanup": True,
            "source_preserved": True,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
