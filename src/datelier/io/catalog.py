"""Worker-side local directory metadata; never decode file payloads here."""

from dataclasses import dataclass
from pathlib import Path

from datelier.io.importing import detect_format
from datelier.io.types import ImportFailure, ImportFormat


@dataclass(frozen=True)
class CatalogFile:
    name: str
    path: Path
    format: ImportFormat


@dataclass(frozen=True)
class DirectoryListing:
    directory: Path
    folders: tuple[Path, ...]
    files: tuple[CatalogFile, ...]
    diagnostics: tuple[str, ...] = ()


def list_directory(path: Path) -> DirectoryListing:
    root = path.expanduser().resolve(strict=True)
    folders: list[Path] = []
    files: list[CatalogFile] = []
    diagnostics: list[str] = []
    for entry in sorted(root.iterdir(), key=lambda entry: entry.name.casefold()):
        try:
            if entry.is_dir():
                folders.append(entry)
            elif entry.is_file():
                try:
                    format = detect_format(entry)
                except ImportFailure:
                    continue
                files.append(CatalogFile(entry.name, entry.resolve(), format))
        except OSError as error:
            diagnostics.append(f"{entry.name}: {error}")
    return DirectoryListing(root, tuple(folders), tuple(files), tuple(diagnostics))
