from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic, sleep

import polars as pl
from PIL import Image

from datelier.core.dataset import Dataset, SourceReference
from datelier.core.jobs import SharedWorkers
from datelier.inspection.references.decode import decode
from datelier.inspection.references.index import IndexProgress, discover, resolve
from datelier.inspection.references.jobs import ReferenceJobs
from datelier.inspection.references.types import ReferenceMapping, ReferenceSettings


def fixture(tmp_path: Path) -> tuple[Path, ReferenceSettings]:
    source = tmp_path / "data" / "table.csv"
    source.parent.mkdir()
    source.write_text("image\na.png\n")
    for folder in ("images", "other"):
        (tmp_path / folder).mkdir()
    Image.new("RGB", (300, 100), "red").save(tmp_path / "images" / "a.png")
    return source, ReferenceSettings(roots=(str(tmp_path),))


def test_exact_then_filename_then_stem_and_explicit_ambiguity(tmp_path: Path) -> None:
    source, settings = fixture(tmp_path)
    image = tmp_path / "images" / "a.png"
    index = discover(source, settings, Event(), IndexProgress())
    assert resolve(source, "image", str(image), settings, None).asset is not None
    assert resolve(source, "image", "../images/a.png", settings, None).asset is not None
    assert resolve(source, "image", "a", settings, index).asset is not None
    assert resolve(source, "image", "a.png", settings, None).asset is None
    Image.new("RGB", (1, 1)).save(tmp_path / "other" / "a.jpg")
    index = discover(source, settings, Event(), IndexProgress())
    ambiguous = resolve(source, "image", "a", settings, index)
    assert len(ambiguous.candidates) == 2 and ambiguous.asset is None
    exact_name = resolve(source, "image", "a.png", settings, index)
    assert exact_name.asset and exact_name.asset.path == image
    mapped = replace(settings, mappings=(ReferenceMapping("image", "a", str(image)),))
    assert resolve(source, "image", "a", mapped, index).asset == exact_name.asset
    image.unlink()
    assert "Mapped file missing" in resolve(source, "image", "a", mapped, index).message


def test_roots_filters_symlink_dedup_missing_and_cooperative_stop(
    tmp_path: Path,
) -> None:
    source, settings = fixture(tmp_path)
    (tmp_path / "images" / "alias.png").symlink_to("a.png")
    (tmp_path / "images" / "loop").symlink_to(tmp_path, target_is_directory=True)
    progress = IndexProgress()
    index = discover(source, settings, Event(), progress)
    assert progress.count == 1
    assert resolve(source, "x", "alias.png", settings, index).asset
    filtered = replace(
        settings, extensions=(".txt",), roots=(str(tmp_path / "gone"), str(tmp_path))
    )
    index = discover(source, filtered, Event(), IndexProgress())
    assert not index.names and index.diagnostics
    stop = Event()
    stop.set()
    assert not discover(source, settings, stop, IndexProgress()).names


def test_thumbnail_text_and_changed_or_corrupt_assets(tmp_path: Path) -> None:
    source, settings = fixture(tmp_path)
    image = tmp_path / "images" / "a.png"
    asset = resolve(source, "x", str(image), settings, None).asset
    assert asset
    preview = decode(asset, 64)
    assert preview.rgba is not None and preview.rgba.shape == (21, 64, 4)
    assert not preview.rgba.flags.writeable
    image.write_bytes(b"broken")
    assert "Cannot preview" in decode(asset, 64).message
    text = tmp_path / "note.txt"
    text.write_bytes(b"hello\n" * 1000)
    asset = resolve(source, "x", str(text), settings, None).asset
    assert asset
    excerpt = decode(asset, 128)
    assert len(excerpt.text.encode()) == 4096 and "truncated" in excerpt.description
    text.write_text("changed")
    assert "changed while decoding" in decode(asset, 128).message


def wait_preview(jobs: ReferenceJobs, column: str, value: str) -> None:
    deadline = monotonic() + 3
    while monotonic() < deadline:
        jobs.poll()
        if jobs.get(column, value)[1] is not None:
            return
        sleep(0.001)
    raise AssertionError(jobs.message)


def test_lazy_revision_source_and_cache_limits(tmp_path: Path) -> None:
    source, settings = fixture(tmp_path)
    data = Dataset.from_source(
        pl.DataFrame({"image": ["a.png"]}), SourceReference(source, 0, 0)
    )
    with SharedWorkers(workers=2) as workers:
        jobs = ReferenceJobs(workers)
        try:
            jobs.configure(settings)
            jobs.bind(source, data.revision)
            assert not jobs.previews
            wait_preview(jobs, "image", "a.png")
            before = jobs.get("image", "a.png")[1]
            assert before and jobs.retained_bytes <= jobs.settings.cpu_bytes
            edited = data.with_role("image", None)
            jobs.bind(source, edited.revision)
            wait_preview(jobs, "image", "a.png")
            assert jobs.get("image", "a.png")[1] is before
            jobs.configure(replace(settings, extensions=(".txt",)))
            assert not jobs.previews
            jobs.close()
            assert jobs.get("image", "a.png") == (None, None)
            jobs.poll()
            assert not jobs.previews and not jobs.busy
        finally:
            jobs.close()


def test_evicted_previews_remain_accessible(tmp_path: Path) -> None:
    source, settings = fixture(tmp_path)
    settings = replace(settings, thumbnail_size=512, cpu_bytes=1024 * 1024)
    paths = [tmp_path / "images" / f"{i}.png" for i in range(3)]
    for path in paths:
        Image.new("RGB", (512, 512)).save(path)
    data = Dataset.from_source(
        pl.DataFrame({"image": [str(p) for p in paths]}), SourceReference(source, 0, 0)
    )
    with SharedWorkers(workers=2) as workers:
        jobs = ReferenceJobs(workers)
        try:
            jobs.configure(settings)
            jobs.bind(source, data.revision)
            for path in paths:
                wait_preview(jobs, "image", str(path))
                assert jobs.retained_bytes <= settings.cpu_bytes
            assert len(jobs.previews) == 1
            wait_preview(jobs, "image", str(paths[0]))
            assert jobs.get("image", str(paths[0]))[1]
            assert jobs.retained_bytes <= settings.cpu_bytes
        finally:
            jobs.close()


def test_explicit_source_reload_drops_same_path_payload_cache(tmp_path: Path) -> None:
    source, settings = fixture(tmp_path)
    data = Dataset.from_source(
        pl.DataFrame({"image": ["a.png"]}), SourceReference(source, 0, 0)
    )
    jobs = ReferenceJobs()
    try:
        jobs.configure(settings)
        jobs.bind(source, data.revision)
        wait_preview(jobs, "image", "a.png")
        assert jobs.previews
        reloaded = Dataset.from_source(data.table, data.source)
        jobs.bind(source, reloaded.revision)
        assert not jobs.previews
        wait_preview(jobs, "image", "a.png")
        assert jobs.previews
    finally:
        jobs.close()
