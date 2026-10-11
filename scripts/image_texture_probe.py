"""Original-resolution worker/window and native texture lifetime prerequisite."""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import polars as pl
from imgui_bundle import hello_imgui, imgui, immapp
from PIL import Image, __version__

from datelier.core import Dataset, SourceReference
from datelier.inspection.images.decoding import ImageStore, prepare_window
from datelier.inspection.images.decoding.sources import prepare_metadata
from datelier.inspection.images.types import ImageDisplay, ImageWindow
from datelier.inspection.references import ReferenceSettings
from datelier.io.arrays import ArrayStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-image-texture.json")
    )
    args = parser.parse_args()
    with TemporaryDirectory(prefix="datelier-image-probe-") as directory:
        root = Path(directory)
        image = root / "image.png"
        Image.new("RGB", (2048, 1536), (180, 80, 30)).save(image)
        source = root / "table.csv"
        source.write_text("image\nimage.png\n")
        stat = source.stat()
        dataset = Dataset.from_source(
            pl.DataFrame({"image": ["image.png"]}),
            SourceReference(source, stat.st_size, stat.st_mtime_ns),
        )
        images, arrays = ImageStore(), ArrayStore()
        with ThreadPoolExecutor(1) as worker:
            started = perf_counter()
            locator, metadata = worker.submit(
                prepare_metadata,
                dataset,
                "probe",
                "records",
                "image",
                0,
                ReferenceSettings(),
                None,
            ).result()
            metadata_seconds = perf_counter() - started
            assert images.temporary_path is None and metadata.width == 2048
            started = perf_counter()
            prepared = worker.submit(
                prepare_window,
                locator,
                metadata,
                ImageWindow(1024, 512, 1024, 1024),
                ImageDisplay(),
                images,
                arrays,
            ).result()
            first_seconds = perf_counter() - started
            started = perf_counter()
            worker.submit(
                prepare_window,
                locator,
                metadata,
                ImageWindow(0, 0),
                ImageDisplay(channel=0),
                images,
                arrays,
            ).result()
            cached_seconds = perf_counter() - started
        assert prepared.rgba.shape == (1024, 1024, 4) and prepared.pixel(1024, 512) == (
            180,
            80,
            30,
        )
        textures: list[hello_imgui.TextureGpu] = []
        frames = uploads = 0

        def show() -> None:
            nonlocal frames, uploads
            frames += 1
            if frames % 5 == 1:
                textures.clear()
                textures.append(
                    hello_imgui.create_texture_gpu_from_rgba_data(prepared.rgba)
                )
                uploads += 1
            imgui.image(imgui.ImTextureRef(textures[0].texture_id()), (256, 256))
            if frames == 30:
                textures.clear()
                hello_imgui.get_runner_params().app_shall_exit = True

        params = hello_imgui.RunnerParams()
        params.app_window_params.window_geometry.size = (350, 350)
        params.ini_filename = str(root / "probe.ini")
        params.fps_idling.enable_idling = False
        params.callbacks.show_gui = show
        immapp.run(params)
        temporary = images.temporary_path
        disk_bytes = images.stored_bytes
        images.cleanup()
        arrays.close()
        assert not textures and temporary is not None and not temporary.exists()
        assert metadata_seconds < 0.5 and first_seconds < 2 and cached_seconds < 0.5
        report = {
            "pillow": __version__,
            "dimensions": [metadata.width, metadata.height],
            "window_shape": list(prepared.raw.shape),
            "pixel": list(prepared.pixel(1024, 512) or ()),
            "metadata_seconds": metadata_seconds,
            "first_window_seconds": first_seconds,
            "cached_window_seconds": cached_seconds,
            "cpu_bytes": prepared.retained_bytes,
            "gpu_bytes": prepared.rgba.nbytes,
            "temporary_bytes": disk_bytes,
            "decodes": images.decodes,
            "frames": frames,
            "uploads": uploads,
            "handles_released": True,
            "temporary_cleanup": True,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
