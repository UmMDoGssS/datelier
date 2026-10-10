"""Only the media presentation commands needed by profile content."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileMedia:
    default_text_column: str | None
    mapped_images: Callable[[], bool]
    image_profile: Callable[[str], None]
    text_profile: Callable[[str], None]
