import importlib
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from datelier.core.column_roles import ColumnRole
from datelier.io.importing import detect_format, load_file
from datelier.io.types import CheckpointOptions, ImportFailure, ImportFormat
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.session_types import SessionFile
from datelier.workspace.storage import reference_source
from datelier.workspace.types import Workspace


@pytest.fixture
def torch() -> ModuleType:
    return pytest.importorskip("torch")


class Unsupported:
    pass


def test_nested_checkpoint_opens_cpu_fake_metadata_without_numpy_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, torch: ModuleType
) -> None:
    path = tmp_path / "nested.ckpt"
    values = torch.arange(24, dtype=torch.float32).reshape(2, 3, 4)
    torch.save(
        {
            "state_dict": {"weight": values, "transpose": values[0].T},
            "optimizer": {0: {"count": 7}},
            "epoch": 2,
            "meta": ["hello", True, None, b"raw"],
            "bf16": torch.tensor([1.5], dtype=torch.bfloat16),
        },
        path,
    )
    original = path.read_bytes()
    original_load = torch.load
    loads: list[dict[str, object]] = []

    def checked_load(*args: object, **kwargs: object) -> object:
        assert kwargs["weights_only"] is True and kwargs["map_location"] == "cpu"
        loaded = original_load(*args, **kwargs)
        assert loaded["state_dict"]["weight"].untyped_storage().device.type == "meta"
        loads.append(kwargs)
        return loaded

    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("Metadata loading must not convert tensor payloads")

    monkeypatch.setattr(torch, "load", checked_load)
    monkeypatch.setattr(torch.Tensor, "numpy", forbidden)
    imported = load_file(path)
    assert imported.format == ImportFormat.CHECKPOINT
    catalog = imported.checkpoint_catalog
    assert catalog and catalog.mapped and len(catalog.tensors) == 3
    info = catalog.tensor("$['state_dict']['weight']")
    assert info.path == ("state_dict", "weight") and info.shape == (2, 3, 4)
    assert info.dtype == "torch.float32" and info.raw_bytes == 96
    assert catalog.tensor("$['state_dict']['transpose']").strides == (1, 4)
    assert imported.object_root is catalog.root
    assert catalog.root.at(("optimizer", 0, "count")).value == 7
    assert catalog.root.at(("meta", 3)).value == b"raw"
    assert imported.dataset.role("tensor").role == ColumnRole.IDENTIFIER
    assert len(loads) == 1 and loads[0]["mmap"] is False
    assert path.read_bytes() == original


def test_legacy_empty_and_cyclic_primitive_checkpoint_metadata(
    tmp_path: Path, torch: ModuleType
) -> None:
    path = tmp_path / "legacy.pth"
    cycle: list[object] = []
    cycle.append(cycle)
    torch.save(
        {"cycle": cycle, "tensor": torch.ones(2)},
        path,
        _use_new_zipfile_serialization=False,
    )
    imported = load_file(path)
    catalog = imported.checkpoint_catalog
    assert catalog and not catalog.mapped
    assert catalog.root.at(("cycle", 0)).kind == "reference"
    assert catalog.root.at(("cycle", 0)).value == "$['cycle']"
    empty = tmp_path / "metadata.pt"
    torch.save({"epoch": 3, "values": []}, empty)
    imported = load_file(empty)
    assert imported.dataset.table.height == 0 and imported.checkpoint_catalog
    assert imported.checkpoint_catalog.root.at(("epoch",)).value == 3


def test_restricted_objects_and_broken_checkpoints_have_local_diagnostics(
    tmp_path: Path,
    torch: ModuleType,
) -> None:
    path = tmp_path / "unsupported.pt"
    torch.save(Unsupported(), path)
    with pytest.raises(ImportFailure, match="restricted tensor loading") as error:
        load_file(path)
    assert "weights_only=False" not in str(error.value)
    path.write_bytes(b"broken checkpoint")
    with pytest.raises(ImportFailure, match="restricted tensor loading"):
        load_file(path)
    with pytest.raises(ImportFailure, match="read source"):
        load_file(tmp_path / "missing.ckpt")


def test_checkpoint_limits_and_options_are_strict_persisted_recipes(
    tmp_path: Path,
    torch: ModuleType,
) -> None:
    path = tmp_path / "limited.pt"
    torch.save({"nested": {"tensor": torch.ones(2)}, -1: "integer key"}, path)
    with pytest.raises(ImportFailure, match="node/depth limits"):
        load_file(path, CheckpointOptions(max_nodes=2))
    with pytest.raises(ImportFailure, match="node/depth limits"):
        load_file(path, CheckpointOptions(max_depth=1))
    options = CheckpointOptions(1234, 34)
    assert decode_record(CheckpointOptions, encode(options)) == options
    imported = load_file(path)
    assert imported.checkpoint_catalog
    assert imported.checkpoint_catalog.root.at((-1,)).value == "integer key"
    file = SessionFile(
        "checkpoint",
        Workspace(
            reference_source(imported.dataset.source), imported.format, imported.options
        ),
        object_path=(-1,),
    )
    file.validate()
    assert decode_record(SessionFile, encode(file)) == file
    for extension in (".pt", ".pth", ".ckpt"):
        assert detect_format(path.with_suffix(extension)) == ImportFormat.CHECKPOINT


@pytest.mark.parametrize("layout", ["sparse", "quantized"])
def test_unsupported_metadata_layouts_remain_restricted_diagnostics(
    tmp_path: Path, torch: ModuleType, layout: str
) -> None:
    path = tmp_path / "layout.pt"
    value = (
        torch.sparse_coo_tensor(
            torch.tensor([[0, 1], [1, 0]]),
            torch.tensor([2.0, 3.0]),
            (2, 2),
            check_invariants=True,
        )
        if layout == "sparse"
        else torch.quantize_per_tensor(torch.tensor([1.0, 2.0]), 0.1, 0, torch.quint8)
    )
    torch.save({"value": value}, path)
    before = path.read_bytes()
    with pytest.raises(ImportFailure, match="Unsupported objects or tensor layouts"):
        load_file(path)
    assert path.read_bytes() == before


def test_missing_optional_extra_is_actionable_and_app_import_stays_lazy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_import = importlib.import_module

    def absent(name: str, package: str | None = None):
        if name == "torch":
            raise ModuleNotFoundError("torch")
        return original_import(name, package)

    path = tmp_path / "missing-extra.pt"
    path.write_bytes(b"placeholder")
    monkeypatch.setattr(importlib, "import_module", absent)
    with pytest.raises(ImportFailure, match="uv sync --locked --extra checkpoints"):
        load_file(path)
    csv = tmp_path / "ordinary.csv"
    csv.write_text("x\n1\n")
    assert load_file(csv).dataset.table["x"].to_list() == [1]
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from datelier.gui.file_session import FileSession; "
            "assert 'torch' not in sys.modules; "
            "session = FileSession.create; print('lazy')",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "lazy"
