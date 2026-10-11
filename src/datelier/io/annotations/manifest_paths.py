"""Local Ultralytics split membership with explicit, deterministic path bases."""

from pathlib import Path

from datelier.core.column_roles import IMAGE_EXTENSIONS
from datelier.inspection.references.types import AssetIdentity
from datelier.io.annotations.source import annotation_source
from datelier.io.media import media_members


def local_path(value: str, base: Path) -> Path:
    if "://" in value:
        raise ValueError(
            "Detection inspection uses local paths; select a local dataset root"
        )
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def split_images(
    value: object, root: Path
) -> tuple[tuple[Path, ...], tuple[AssetIdentity, ...]]:
    parts = value if isinstance(value, list) else [value]
    paths: list[Path] = []
    sources: list[AssetIdentity] = []
    for item in parts:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Manifest splits require local paths or lists of paths")
        path = local_path(item, root)
        if path.is_dir():
            paths.extend(
                path / member
                for member in media_members(path)
                if Path(member).suffix.lower() in IMAGE_EXTENSIONS
            )
        elif path.suffix.lower() == ".txt":
            with annotation_source(path) as (asset, stream):
                for line in stream.read().decode("utf-8-sig").splitlines():
                    if line.strip():
                        paths.append(
                            local_path(
                                line.strip(),
                                path.parent if line.strip().startswith("./") else root,
                            )
                        )
            sources.append(asset)
        elif path.suffix.lower() in IMAGE_EXTENSIONS:
            paths.append(path)
        else:
            raise ValueError(f"Split path is missing or unsupported: {path}")
    return tuple(paths), tuple(sources)


def label_path(image: Path) -> Path:
    parts = list(image.parts)
    positions = [i for i, part in enumerate(parts[:-1]) if part == "images"]
    if positions:
        parts[positions[-1]] = "labels"
    return Path(*parts).with_suffix(".txt")
