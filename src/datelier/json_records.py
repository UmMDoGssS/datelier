"""Streaming JSON array grammar using the standard decoder for each value."""

import json
from collections.abc import Callable, Iterator
from io import TextIOWrapper
from typing import BinaryIO, cast

CHUNK_CHARACTERS = 64 * 1024


def array_records(
    source: BinaryIO,
    object_hook: Callable[[list[tuple[str, object]]], dict[str, object]],
    constant: Callable[[str], object],
) -> Iterator[object]:
    decoder = json.JSONDecoder(object_pairs_hook=object_hook, parse_constant=constant)
    with TextIOWrapper(source, encoding="utf-8") as text:
        buffer = ""
        position = 0
        eof = False

        def fill() -> None:
            nonlocal buffer, position, eof
            chunk = text.read(CHUNK_CHARACTERS)
            buffer = buffer[position:] + chunk
            position = 0
            eof = not chunk

        def peek() -> str | None:
            nonlocal position
            while True:
                while position < len(buffer) and buffer[position] in " \r\n\t":
                    position += 1
                if position < len(buffer):
                    return buffer[position]
                if eof:
                    return None
                fill()

        if peek() != "[":
            raise ValueError(
                "Expected a JSON array of record objects; "
                "use JSONL for one object per line."
            )
        position += 1
        if peek() != "]":
            while True:
                while True:
                    try:
                        # The decoder is untyped; callers validate every returned value.
                        value, end = decoder.raw_decode(buffer, position)
                        break
                    except json.JSONDecodeError:
                        if eof:
                            raise
                        fill()
                position = end
                yield cast(object, value)
                separator = peek()
                if separator == "]":
                    break
                if separator != ",":
                    raise ValueError(
                        "Expected a comma or closing ] after a JSON record."
                    )
                position += 1
                if peek() == "]":
                    raise ValueError("Trailing commas are invalid JSON.")
        position += 1
        if peek() is not None:
            raise ValueError(
                "Extra data after the JSON array; use JSONL for separate records."
            )
