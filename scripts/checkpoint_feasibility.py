"""CPU/Python checkpoint loading gate, runnable in an isolated optional environment."""

import argparse
import importlib
import json
import platform
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter


class Unsupported:
    """A plain non-allowlisted fixture; restricted loading must reject it."""


def verify() -> dict[str, object]:
    # Keep this optional dependency boundary isolated from ordinary app imports.
    torch = importlib.import_module("torch")
    fake = importlib.import_module("torch._subclasses.fake_tensor")
    begin = perf_counter()
    with TemporaryDirectory(prefix="datelier-checkpoint-gate-") as directory:
        root = Path(directory)
        path = root / "nested.ckpt"
        original = torch.arange(120, dtype=torch.float32).reshape(2, 3, 20)
        torch.save(
            {
                "state_dict": {"weight": original, "transpose": original[0].T},
                "epoch": 7,
                "metadata": ["sample", True, None],
                "bf16": torch.tensor([1.5, -2.25], dtype=torch.bfloat16),
            },
            path,
        )
        before = path.read_bytes()
        with fake.FakeTensorMode():
            metadata = torch.load(path, weights_only=True, map_location="cpu")
        assert tuple(metadata["state_dict"]["weight"].shape) == (2, 3, 20)
        assert metadata["state_dict"]["weight"].untyped_storage().device.type == "meta"
        assert metadata["epoch"] == 7 and metadata["metadata"] == ["sample", True, None]
        loaded = torch.load(path, weights_only=True, map_location="cpu", mmap=True)
        values = loaded["state_dict"]["weight"]
        assert values.device.type == "cpu" and torch.equal(values[1], original[1])
        assert loaded["state_dict"]["transpose"].stride() == (1, 20)
        assert loaded["bf16"].float().tolist() == [1.5, -2.25]
        unsupported = root / "unsupported.pt"
        torch.save(Unsupported(), unsupported)
        rejected = False
        try:
            with fake.FakeTensorMode():
                torch.load(unsupported, weights_only=True, map_location="cpu")
        except Exception:
            rejected = True
        assert rejected
        legacy = root / "legacy.pth"
        torch.save({"weight": original}, legacy, _use_new_zipfile_serialization=False)
        with fake.FakeTensorMode():
            legacy_meta = torch.load(legacy, weights_only=True, map_location="cpu")
        assert tuple(legacy_meta["weight"].shape) == (2, 3, 20)
        assert legacy_meta["weight"].untyped_storage().device.type == "meta"
        legacy_values = torch.load(
            legacy, weights_only=True, map_location="cpu", mmap=False
        )
        assert torch.equal(legacy_values["weight"], original)
        assert path.read_bytes() == before
        report: dict[str, object] = {
            "python": platform.python_version(),
            "platform": platform.system(),
            "machine": platform.machine(),
            "torch": str(torch.__version__),
            "cuda_build": torch.version.cuda,
            "metadata_storage": "meta",
            "cpu_mapped_values": True,
            "nested_metadata": True,
            "noncontiguous_values": True,
            "bfloat16_values": True,
            "restricted_object_rejection": True,
            "legacy_metadata_only": True,
            "legacy_explicit_values": True,
            "source_preserved": True,
            "elapsed_ms": (perf_counter() - begin) * 1000,
        }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
