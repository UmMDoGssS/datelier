"""Header-only association latency/memory, original geometry and preservation."""

import argparse
import hashlib
import json
import resource
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import perf_counter
from unittest.mock import patch

from PIL import Image

from datelier.inspection.annotations.prepare import prepare_annotations
from datelier.inspection.annotations.profiles import prepare_profiles
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
    ImageMatch,
)
from datelier.inspection.annotations.types import AnnotationFormat
from datelier.inspection.images.profile_types import ImageProgress
from datelier.inspection.references.types import ReferenceSettings
from datelier.io.importing import load_inspectable_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-annotations-resource.json")
    )
    args = parser.parse_args()
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    with TemporaryDirectory(prefix="datelier-annotation-bench-") as directory:
        root = Path(directory)
        count, per_image = 100, 100
        images = []
        boxes = []
        lines = ["image,id"]
        for image in range(count):
            path = root / f"{image}.png"
            Image.new("RGB", (256, 128), (image, 20, 30)).save(path)
            images.append(
                {"id": image, "file_name": path.name, "width": 256, "height": 128}
            )
            lines.append(f"{path.name},{image}")
            for box in range(per_image):
                boxes.append(
                    {
                        "id": image * per_image + box,
                        "image_id": image,
                        "category_id": box % 3,
                        "bbox": [box, 10, 20, 40],
                    }
                )
        (root / "source.csv").write_text("\n".join(lines) + "\n")
        source = root / "boxes.json"
        source.write_text(
            json.dumps(
                {
                    "images": images,
                    "annotations": boxes,
                    "categories": [
                        {"id": index, "name": str(index)} for index in range(3)
                    ],
                }
            )
        )
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.iterdir()
        }
        settings = AnnotationSettings(
            "image",
            (
                AnnotationSource(
                    "truth",
                    str(source),
                    AnnotationFormat.COCO,
                    match=ImageMatch.COLUMN,
                    key_column="id",
                ),
            ),
        )
        with patch.object(
            Image.Image, "load", side_effect=AssertionError("pixels decoded")
        ):
            dataset = load_inspectable_file(root / "source.csv").dataset
            started = perf_counter()
            prepared = prepare_annotations(
                dataset,
                "file",
                "",
                settings,
                ReferenceSettings(),
                None,
                Event(),
                ImageProgress(),
            )
            seconds = perf_counter() - started
            started = perf_counter()
            profiles = prepare_profiles(prepared, 32, Event(), ImageProgress())
            profile_seconds = perf_counter() - started
        prepared_source = prepared.sources[0]
        assert (
            not prepared_source.error
            and len(prepared_source.boxes) == count * per_image
        )
        assert all(item.status == "Ready" for item in prepared_source.images)
        assert prepared_source.boxes[-1].box.xyxy == (99, 10, 119, 50)
        profile = profiles.sources[0]
        assert [item.count for item in profile.classes] == [3400, 3300, 3300]
        assert all(len(item.row_ids) == 100 for item in profile.classes)
        assert [item.mean for item in profile.summaries] == [20.0, 40.0, 800.0, 0.5]
        assert before.keys() == set(root.iterdir())
        assert all(
            hashlib.sha256(path.read_bytes()).hexdigest() == value
            for path, value in before.items()
        )
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        assert (
            seconds < 5 and profile_seconds < 5 and peak - baseline < 64 * 1024 * 1024
        )
        report = {
            "images": count,
            "boxes": count * per_image,
            "seconds": seconds,
            "profile_seconds": profile_seconds,
            "profile_rows": profile.records.height,
            "peak_rss_increase_bytes": peak - baseline,
            "image_pixels_decoded": 0,
            "temporary_cache_bytes": 0,
            "sources_preserved": True,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
