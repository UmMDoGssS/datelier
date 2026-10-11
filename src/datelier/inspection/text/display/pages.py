"""Bounded original-text pages with exact source offsets and token highlights."""

from dataclasses import dataclass

from datelier.inspection.text.display.viewport import TextViewport
from datelier.inspection.text.types import TextOrigin, TokenizedDocument


@dataclass(frozen=True)
class TextRun:
    text: str
    start: int
    end: int
    highlighted: bool


@dataclass(frozen=True)
class TextLine:
    start: int
    runs: tuple[TextRun, ...]


@dataclass(frozen=True)
class TextPage:
    origin: TextOrigin
    viewport: TextViewport
    start: int
    end: int
    lines: tuple[TextLine, ...]
    selected_source: str
    selected_span: tuple[int, int] | None
    selected_piece: str
    piece_start: int
    piece_length: int


def display_text(raw: str) -> str:
    return "".join(chr(0x2400 + ord(ch)) if ord(ch) < 32 else ch for ch in raw)


def prepare_text_page(document: TokenizedDocument, viewport: TextViewport) -> TextPage:
    viewport.validate()
    original = document.document.text
    start = min(viewport.start, len(original))
    end = min(start + viewport.count, len(original))
    span: tuple[int, int] | None = None
    selected_source = ""
    piece = ""
    if 0 <= viewport.selected_token < len(document.tokens):
        token = document.tokens[viewport.selected_token]
        piece = token.piece
        span = (token.start, token.end)
        selected_source = original[token.start : min(token.end, token.start + 256)]
    lines: list[TextLine] = []
    position = start
    while position < end:
        newline = original.find("\n", position, min(position + 64, end))
        stop = newline + 1 if newline >= 0 else min(position + 64, end)
        cuts = {position, stop}
        if span is not None:
            cuts.update(point for point in span if position < point < stop)
        points = sorted(cuts)
        runs = tuple(
            TextRun(
                display_text(original[a:b]),
                a,
                b,
                span is not None and span[0] <= a < span[1],
            )
            for a, b in zip(points, points[1:], strict=False)
        )
        lines.append(TextLine(position, runs))
        position = stop
    return TextPage(
        document.document.origin,
        viewport,
        start,
        end,
        tuple(lines),
        selected_source,
        span,
        piece[viewport.piece_start : viewport.piece_start + 256],
        min(viewport.piece_start, len(piece)),
        len(piece),
    )
