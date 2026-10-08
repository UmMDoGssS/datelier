"""Deterministic mixed-source fixtures shared by session and installed-wheel probes."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl
import soundfile as sf
from PIL import Image


@dataclass(frozen=True)
class MultimodalFixtures:
    train: Path
    test: Path
    arrays: Path
    assets: tuple[Path, ...]

    @property
    def sources(self) -> tuple[Path, ...]:
        return self.train, self.test, self.arrays, *self.assets


def make_multimodal(root: Path) -> MultimodalFixtures:
    root.mkdir(parents=True, exist_ok=True)
    assets = []
    for index, (width, amplitude, rate, seconds) in enumerate(
        ((16, 0.25, 8000, 1), (24, 0.5, 8000, 2), (32, 0.75, 16000, 3))
    ):
        image, audio = root / f"image-{index}.png", root / f"audio-{index}.wav"
        Image.new("RGB", (width, 12), (10 + 70 * index, 20, 30)).save(image)
        values = amplitude * np.sin(2 * np.pi * 500 * np.arange(rate * seconds) / rate)
        sf.write(audio, np.stack((values, values), axis=1), rate, subtype="FLOAT")
        assets.extend((image, audio))
    train, test = root / "train.csv", root / "test.csv"
    captions = ("alpha e\u0301 中🙂", "beta beta", "third record")
    for path, rows in ((train, (0, 1)), (test, (2, 0, 1))):
        pl.DataFrame(
            {
                "label": [index + 1 for index in rows],
                "caption": [captions[index] for index in rows],
                "image": [f"image-{index}.png" for index in rows],
                "audio": [f"audio-{index}.wav" for index in rows],
                "score": [float(index + 1) for index in rows],
            }
        ).write_csv(path)
    arrays = root / "records.npz"
    images = np.empty((3, 12, 16, 3), dtype=np.uint8)
    waves = np.empty((3, 8000, 2), dtype=np.float32)
    positions = np.arange(8000) / 8000
    for row in range(3):
        images[row] = (10 + 70 * row, 20, 30)
        wave = (0.25 + 0.25 * row) * np.sin(2 * np.pi * 500 * positions)
        waves[row, :, 0] = waves[row, :, 1] = wave
    np.savez_compressed(
        arrays,
        images=images,
        audio=waves,
        labels=np.array([3, 1, 2]),
        captions=np.array(["array a 中🙂", "array b e\u0301", "array c beta"]),
    )
    return MultimodalFixtures(train, test, arrays, tuple(assets))
