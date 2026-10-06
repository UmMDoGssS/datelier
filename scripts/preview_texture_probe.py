"""Pillow/Python decode and native GPU lifetime prerequisite for lazy previews."""

import gc
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from imgui_bundle import hello_imgui, imgui, immapp
from PIL import Image, __version__


def main() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "probe.png"
        Image.new("RGB", (400, 200), (180, 80, 30)).save(path)

        def decode() -> np.ndarray:
            with Image.open(path) as image:
                image.thumbnail((128, 128))
                return np.asarray(image.convert("RGBA")).copy()

        with ThreadPoolExecutor(1) as worker:
            rgba = worker.submit(decode).result()
        assert rgba.shape == (64, 128, 4) and rgba.dtype == np.uint8
        textures: list[hello_imgui.TextureGpu] = []
        frames = 0

        def show() -> None:
            nonlocal frames
            frames += 1
            if frames % 5 == 1:
                textures.clear()
                gc.collect()
                textures.append(hello_imgui.create_texture_gpu_from_rgba_data(rgba))
            imgui.image(imgui.ImTextureRef(textures[0].texture_id()), (128, 64))
            if frames == 30:
                textures.clear()
                hello_imgui.get_runner_params().app_shall_exit = True

        immapp.run(show, window_size=(300, 200), fps_idle=0)
        assert not textures
        print(
            json.dumps(
                {
                    "pillow": __version__,
                    "frames": frames,
                    "uploads": 6,
                    "worker_decode": True,
                    "handles_released": True,
                }
            )
        )


if __name__ == "__main__":
    main()
