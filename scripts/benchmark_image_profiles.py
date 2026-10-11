"""Fresh-process image/folder and array profile memory, latency and cleanup gates."""

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

from datelier.core import Dataset
from datelier.inspection.arrays import ArrayLayout, ArrayRecordMapping
from datelier.inspection.images.decoding import ImageStore
from datelier.inspection.images.profiles import (
    ImageProfileSettings,
    ImageProgress,
    PixelScope,
)
from datelier.inspection.images.profiles.prepare import prepare_image_profile
from datelier.inspection.references import AssetIdentity, ReferenceSettings
from datelier.io.arrays import ArrayStore
from datelier.io.arrays.metadata import inspect_arrays
from datelier.io.media import load_media
from datelier.io.types import MediaOptions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("folder", "array"), default="folder")
    parser.add_argument("--sample", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/datelier-image-profile-resources.json"),
    )
    args = parser.parse_args()
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    peak_disk = active_files = retained_after_lease = decodes = 0
    temporary_paths: set[Path] = set()
    original = ImageStore.open_file

    @contextmanager
    def measured(
        self: ImageStore,
        asset: AssetIdentity,
        stopped: Callable[[], bool] | None = None,
    ) -> Iterator[NDArray[np.generic]]:
        nonlocal peak_disk, active_files, retained_after_lease, decodes
        with original(self, asset, stopped) as raw:
            if self.temporary_path is not None:
                temporary_paths.add(self.temporary_path)
                active_files = max(
                    active_files, len(list(self.temporary_path.iterdir()))
                )
            peak_disk = max(peak_disk, self.stored_bytes)
            yield raw
        retained_after_lease = max(retained_after_lease, self.stored_bytes)
        decodes = self.decodes

    with TemporaryDirectory(prefix="datelier-image-profile-bench-") as directory:
        root = Path(directory)
        count = 100
        arrays = ArrayStore(retained_bytes=1024 * 1024)
        catalog = mapping = None
        if args.kind == "folder":
            for index in range(count):
                mode = ("L", "RGB", "RGBA")[index % 3]
                value = (
                    index
                    if mode == "L"
                    else (index, 20, 30)
                    if mode == "RGB"
                    else (index, 20, 30, 64)
                )
                Image.new(mode, (256, 256), value).save(root / f"{index:03}.png")
            (root / "corrupt.png").write_bytes(b"corrupt")
            members = tuple(f"{index:03}.png" for index in range(count)) + (
                "corrupt.png",
                "missing.png",
            )
            start = perf_counter()
            dataset = load_media(root, MediaOptions(manifest=members)).dataset
            metadata_seconds = perf_counter() - start
            column = "path"
            before = {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.iterdir()
            }
        else:
            pixels = np.empty((count, 256, 256, 3), dtype=np.uint8)
            for index in range(count):
                pixels[index] = (index, 20, 30)
            source = root / "images.npz"
            np.savez_compressed(source, images=pixels, unselected=np.ones((100, 100)))
            del pixels
            start = perf_counter()
            catalog = inspect_arrays(source)
            metadata_seconds = perf_counter() - start
            dataset = Dataset.from_source(
                pl.DataFrame({"record_index": range(count)}), catalog.source
            )
            mapping = ArrayRecordMapping(
                "images", layout=ArrayLayout.IMAGE, display_axes=(1, 2), channel_axis=3
            )
            column = "images"
            before = {source: hashlib.sha256(source.read_bytes()).hexdigest()}
        settings = ImageProfileSettings(
            column,
            pixels=PixelScope.SAMPLE if args.sample else PixelScope.EXACT,
            pixel_count=1024,
        )
        start = perf_counter()
        with patch.object(ImageStore, "open_file", new=measured):
            result = prepare_image_profile(
                dataset,
                "benchmark",
                args.kind,
                settings,
                (),
                ReferenceSettings(),
                None,
                arrays,
                Event(),
                ImageProgress(),
                catalog,
                mapping,
            )
        seconds = perf_counter() - start
        if arrays.temporary_path is not None:
            temporary_paths.add(arrays.temporary_path)
        arrays_retained = arrays.stored_bytes
        arrays.close()
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        assert result.ready == count and result.total_pixels == count * 256 * 256
        assert result.profiled_pixels == count * (1024 if args.sample else 256 * 256)
        assert result.sampled_pixels == args.sample
        if args.kind == "folder":
            assert result.unresolved == result.failures == 1
            assert active_files == 1 and retained_after_lease == 0
            assert decodes == 2 * count
        else:
            assert arrays.extractions == 1 and arrays_retained == 0
            assert result.summaries[0].mean == 49.5
        assert seconds < 10 and metadata_seconds < 0.5
        assert peak_rss - baseline < 96 * 1024 * 1024
        assert all(not path.exists() for path in temporary_paths)
        assert all(
            hashlib.sha256(path.read_bytes()).hexdigest() == digest
            for path, digest in before.items()
        )
        report = {
            "kind": args.kind,
            "sampled": args.sample,
            "images": count,
            "dimensions": [256, 256],
            "metadata_seconds": metadata_seconds,
            "profile_seconds": seconds,
            "baseline_rss_bytes": baseline,
            "peak_rss_bytes": peak_rss,
            "rss_increase_bytes": peak_rss - baseline,
            "result_bytes": result.retained_bytes,
            "peak_decoded_disk_bytes": peak_disk,
            "peak_decoded_files": active_files,
            "retained_decoded_bytes": retained_after_lease,
            "array_extractions": arrays.extractions,
            "array_extracted_bytes": arrays.extracted_bytes,
            "array_retained_bytes": arrays_retained,
            "profiled_pixels": result.profiled_pixels,
            "total_pixels": result.total_pixels,
            "unresolved": result.unresolved,
            "failures": result.failures,
            "cleanup": True,
            "source_preserved": True,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
