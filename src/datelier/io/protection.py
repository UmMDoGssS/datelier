"""Worker-side preservation of individual sources and media-folder members."""

from pathlib import Path

from datelier.io.media.manifest import MEDIA_EXTENSIONS, media_members


def destination_is_source(destination: Path, source: Path) -> bool:
    source = source.expanduser().resolve()
    if destination == source or (
        destination.exists() and source.exists() and destination.samefile(source)
    ):
        return True
    if not source.is_dir():
        return False
    if (
        destination.is_relative_to(source)
        and destination.suffix.lower() in MEDIA_EXTENSIONS
    ):
        return True
    # Canonical/same-file checks protect aliases and hardlinks outside the folder.
    for member in media_members(source):
        asset = (source / member).resolve()
        if destination == asset or (
            destination.exists() and asset.exists() and destination.samefile(asset)
        ):
            return True
    return False
