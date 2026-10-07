"""Serializable original-text navigation and token-selection settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextViewport:
    start: int = 0
    count: int = 2048
    selected_token: int = -1
    piece_start: int = 0

    def validate(self) -> None:
        if (
            min(self.start, self.piece_start) < 0
            or not 128 <= self.count <= 8192
            or self.selected_token < -1
        ):
            raise ValueError(
                "Text viewport needs a nonnegative offset, "
                "128–8192 code points and a valid token index"
            )
