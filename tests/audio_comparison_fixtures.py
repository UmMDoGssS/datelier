"""Unequal known audio collections with stereo, silence and reference failures."""

from pathlib import Path

import numpy as np
import polars as pl
import soundfile as sf

from datelier.core import Dataset, SourceReference
from datelier.inspection.audio.collections.settings import (
    AudioCollectionSettings,
    AudioProfileMode,
)
from datelier.inspection.audio.comparisons import (
    AudioComparisonSettings,
    AudioComparisonSource,
)
from datelier.inspection.audio.comparisons.types import AudioComparisonInput


def table(path: Path, references: list[str | None]) -> Dataset:
    path.write_text("audio\n")
    stat = path.stat()
    return Dataset.from_source(
        pl.DataFrame({"audio": references}, schema_overrides={"audio": pl.String}),
        SourceReference(path, stat.st_size, stat.st_mtime_ns),
    )


def fixture(
    root: Path, mode: AudioProfileMode = AudioProfileMode.SIGNAL
) -> tuple[tuple[AudioComparisonInput, ...], AudioComparisonSettings]:
    for name, frames, rate, amplitude in (
        ("a", 4, 4, 0.25),
        ("b", 8, 4, 0.5),
        ("c", 8, 8, 0.0),
    ):
        sf.write(
            root / f"{name}.wav",
            np.tile([amplitude, -amplitude], (frames, 1)),
            rate,
            subtype="DOUBLE",
        )
    (root / "corrupt.wav").write_bytes(b"corrupt")
    datasets = (
        table(root / "train.csv", ["a.wav", "b.wav"]),
        table(
            root / "test.csv", ["c.wav", "b.wav", None, "missing.wav", "corrupt.wav"]
        ),
    )
    sources = tuple(
        AudioComparisonSource(name, AudioCollectionSettings("audio", mode=mode))
        for name in ("train", "test")
    )
    recipe = AudioComparisonSettings(sources, 2)
    inputs = tuple(
        AudioComparisonInput(source, dataset, source.file_id, "records")
        for source, dataset in zip(sources, datasets, strict=True)
    )
    return inputs, recipe
