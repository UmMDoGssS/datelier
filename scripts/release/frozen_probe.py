"""Frozen verification entry; uses only modules collected for the production app.

The helper is not shipped. Its spawned processes execute the production binary,
so a missing freeze_support dispatch fails this gate rather than going unnoticed.
"""

import argparse
import json
import multiprocessing as mp
import sys
from importlib.metadata import version
from pathlib import Path
from time import monotonic, sleep
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datelier.core import Dataset
    from datelier.io.types import ImportResult


def analyses(data: Dataset) -> list[str]:
    import numpy as np

    from datelier.analysis.jobs import AnalysisJobs
    from datelier.analysis.types import (
        AnalysisRequest,
        KMeansParameters,
        PCAParameters,
        TSNEParameters,
        UMAPParameters,
    )

    jobs = AnalysisJobs()
    completed: list[str] = []

    def wait() -> None:
        deadline = monotonic() + 180
        while jobs.busy and monotonic() < deadline:
            jobs.poll(data.revision)
            sleep(0.01)
        assert not jobs.busy, jobs.message

    try:
        for method in (
            PCAParameters(),
            KMeansParameters(),
            TSNEParameters(perplexity=5, iterations=250),
            UMAPParameters(neighbors=5),
        ):
            request = AnalysisRequest(("x", "y", "z"), method)
            jobs.request(data, request)
            wait()
            result = jobs.latest
            assert result is not None and result.provenance.request == request, (
                jobs.message
            )
            np.testing.assert_array_equal(result.row_ids, data.row_ids.to_numpy())
            assert all(value for _, value in result.provenance.versions)
            completed.append(request.algorithm.value)
            print(f"Verified frozen {request.algorithm}", flush=True)
        previous = jobs.latest
        jobs.request(data, AnalysisRequest(("x", "y", "z"), TSNEParameters(), seed=123))
        deadline = monotonic() + 10
        while not jobs.phase.startswith("Loading libraries") and monotonic() < deadline:
            sleep(0.005)
        assert jobs.busy and jobs.phase.startswith("Loading libraries"), jobs.phase
        jobs.cancel()
        wait()
        assert jobs.latest is previous and "cancelled" in jobs.message.lower()
    finally:
        jobs.close()
    return completed


def assets(root: Path) -> None:
    import numpy as np
    import soundfile as sf
    from PIL import Image

    Image.new("RGB", (4, 3), (12, 34, 56)).save(root / "image.png")
    rate = 24000
    tone = 0.25 * np.sin(2 * np.pi * 440 * np.arange(rate) / rate)
    for name, subtype in (
        ("WAV", "PCM_16"),
        ("FLAC", "PCM_16"),
        ("OGG", "VORBIS"),
        ("MP3", "MPEG_LAYER_III"),
    ):
        path = root / f"tone.{name.lower()}"
        sf.write(path, tone, rate, format=name, subtype=subtype)
        decoded, actual_rate = sf.read(path)
        assert actual_rate == rate and len(decoded) == rate
        assert abs(float(np.sqrt(np.square(decoded).mean())) - 0.25 / 2**0.5) < 0.015


def media(root: Path, data: Dataset) -> None:
    import numpy as np
    import sounddevice as sd
    import tokenizers
    import torch

    from datelier.inspection.arrays.settings import SliceSettings
    from datelier.inspection.arrays.slices import prepare_slice
    from datelier.inspection.audio.decoding import (
        audio_blocks,
        audio_metadata,
        locate_audio,
    )
    from datelier.inspection.checkpoints.slices import prepare_tensor_slice
    from datelier.inspection.images.decoding import ImageStore
    from datelier.inspection.images.decoding.sources import file_metadata, locate_image
    from datelier.inspection.references import ReferenceSettings
    from datelier.inspection.text.tokenizers import import_tokenizer
    from datelier.inspection.text.tokenizers.prepare import prepare_document
    from datelier.inspection.text.types import (
        TextSettings,
        TextSource,
        TokenMode,
        TokenSettings,
    )
    from datelier.io.annotations.yaml_source import decode_manifest
    from datelier.io.arrays import ArrayStore
    from datelier.io.arrays.metadata import inspect_arrays
    from datelier.io.checkpoints.storage import CheckpointStore
    from datelier.io.importing import load_file

    assert sd.get_portaudio_version()[0] > 0 and torch.version.cuda is None
    assert decode_manifest("names: [cat, dog]\n") == {"names": ["cat", "dog"]}
    references = ReferenceSettings()
    images = ImageStore()
    arrays = ArrayStore(retained_bytes=1)
    checkpoints = CheckpointStore(retained_bytes=1)
    try:
        image = locate_image(data, "file", "", "image", 0, references, None)
        assert image.asset and file_metadata(image.asset).width == 4
        with images.open_file(image.asset) as pixels:
            assert pixels[0, 0].tolist() == [12, 34, 56]
        audio = locate_audio(data, "file", "", "audio", 0, references, None)
        metadata = audio_metadata(audio)
        with audio_blocks(audio, metadata, arrays) as blocks:
            assert sum(len(block.samples) for block in blocks) == 24000
        path = root / "values.npz"
        np.savez_compressed(path, values=np.arange(12).reshape(3, 4))
        settings = SliceSettings("values", axes=(0, 1), counts=(3, 4))
        result = prepare_slice(arrays, inspect_arrays(path), settings)
        np.testing.assert_array_equal(result.raw, np.arange(12).reshape(3, 4))
        path = root / "dense.pt"
        torch.save({"weight": torch.arange(12).reshape(3, 4)}, path)
        catalog = load_file(path).checkpoint_catalog
        assert catalog is not None
        result = prepare_tensor_slice(
            checkpoints,
            catalog,
            SliceSettings("$['weight']", axes=(0, 1), counts=(3, 4)),
        ).view
        np.testing.assert_array_equal(result.raw, np.arange(12).reshape(3, 4))
        tokenizer = tokenizers.Tokenizer(tokenizers.models.BPE(unk_token="[UNK]"))
        tokenizer.pre_tokenizer = tokenizers.pre_tokenizers.Whitespace()
        tokenizer.train_from_iterator(
            ["hello world", "hello café", "你好 🙂"],
            tokenizers.trainers.BpeTrainer(vocab_size=32, special_tokens=["[UNK]"]),
        )
        path = root / "tokenizer.json"
        tokenizer.save(str(path))
        document = prepare_document(
            data,
            "file",
            TextSettings(
                "text",
                TextSource.INLINE,
                tokens=TokenSettings(
                    mode=TokenMode.BPE, artifact=import_tokenizer(path)
                ),
            ),
            references,
            None,
        )
        assert document.tokens and document.document.text == "hello café 你好 🙂"
    finally:
        images.cleanup()
        arrays.close()
        checkpoints.close()


def workspace(root: Path, imported: ImportResult) -> Path:
    from datelier.pipeline.operations import Sort
    from datelier.workspace.sessions import SessionFile, SessionWorkspace
    from datelier.workspace.sessions.restore import (
        SourceRecovery,
        restore_session_workspace,
    )
    from datelier.workspace.sessions.storage import save_session_workspace
    from datelier.workspace.single import Workspace
    from datelier.workspace.single.storage import reference_source

    path = root / "session.datelier"
    recipe = Workspace(
        reference_source(imported.dataset.source),
        imported.format,
        imported.options,
        history=(Sort(("x",)),),
        cursor=1,
    )
    save_session_workspace(
        path, SessionWorkspace((SessionFile("file", recipe),), "file")
    )
    restored = restore_session_workspace(path)
    assert restored.files[0].restored is not None
    moved = imported.dataset.source.path.rename(root / "moved.csv")
    assert restore_session_workspace(path).files[0].restored is None
    recovered = restore_session_workspace(
        path, recoveries=(SourceRecovery("file", moved),)
    )
    assert recovered.files[0].restored is not None
    save_session_workspace(path, recovered.workspace)
    return path


def native(root: Path, saved: Path) -> None:
    from imgui_bundle import hello_imgui, imgui
    from PIL import Image

    from datelier.application.sessions import EditorController
    from datelier.gui.app import InspectionEvidence, run_gui
    from datelier.gui.components.probe import GuiProbe
    from datelier.gui.fonts import FALLBACK_FONTS
    from datelier.gui.records.media.sampling import NearestSampling

    assert FALLBACK_FONTS[-1].is_file()
    assert FALLBACK_FONTS[-1].with_name("OFL-NotoEmoji.txt").is_file()
    sampler = NearestSampling()
    done = False

    def frame(
        editor: EditorController, probe: GuiProbe, evidence: InspectionEvidence
    ) -> None:
        nonlocal done
        try:
            assert evidence.frames < 600
            if evidence.frames < 40:
                imgui.begin("Frozen image sampling")
                with sampler.draw():
                    imgui.get_window_draw_list().add_rect_filled(
                        (10, 10), (20, 20), 0xFFFFFFFF
                    )
                imgui.end()
            elif editor.current.inspection and editor.workers.pending == 0:
                assert editor.current.inspection.dataset.table.height == 80
                assert not editor.current.analysis.jobs.results
                assert editor.playback.snapshot.request is None
                sampler.close()
                done = True
                hello_imgui.get_runner_params().app_shall_exit = True
        except BaseException:
            sampler.close()
            raise

    run_gui(
        initial_workspace=saved,
        preferences_path=root / "preferences.json",
        on_probe_frame=frame,
    )
    assert done
    Image.fromarray(hello_imgui.final_app_window_screenshot()[:, :, :3]).save(
        root / "frozen-native.png"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    assert getattr(sys, "frozen", False), "Run the built datelier-verify executable"
    assert "torch" not in sys.modules and "sounddevice" not in sys.modules
    internal = Path(sys.executable).parent / "_internal"
    assert all(Path(path).resolve().is_relative_to(internal) for path in sys.path)
    mp.set_executable(str(Path(sys.executable).with_name("datelier")))
    import numpy as np
    import polars as pl

    from datelier.io.importing import load_file

    args.output.mkdir(parents=True, exist_ok=True)
    assets(args.output)
    source = args.output / "data.csv"
    rng = np.random.default_rng(42)
    table = pl.DataFrame({name: rng.normal(size=80) for name in ("x", "y", "z")})
    table = table.with_columns(
        pl.lit("image.png").alias("image"),
        pl.lit("tone.wav").alias("audio"),
        pl.lit("hello café 你好 🙂").alias("text"),
    )
    table.write_csv(source)
    before = source.read_bytes()
    imported = load_file(source)
    data = imported.dataset
    report = {
        "version": version("datelier"),
        "analyses": analyses(data),
        "cancelled_worker_joined": True,
    }
    assert source.read_bytes() == before
    media(args.output, data)
    saved = workspace(args.output, imported)
    assert (args.output / "moved.csv").read_bytes() == before
    if args.native:
        native(args.output, saved)
    report.update(
        media=True,
        checkpoints=True,
        workspace_relink=True,
        source_preserved=True,
        isolated_imports=True,
        native=args.native,
    )
    (args.output / "frozen-verification.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report))


if __name__ == "__main__":
    mp.freeze_support()
    main()
