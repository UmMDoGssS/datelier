"""Bounded XML parsing for explicit relative child and descendant paths."""

import re
from collections.abc import Iterator
from typing import BinaryIO
from xml.etree import ElementTree as ET

from datelier.import_types import XmlOptions


class RecordPath:
    def __init__(self, options: XmlOptions) -> None:
        path = options.record_path
        self.descendant = path.startswith(".//")
        if path == ".":
            self.parts: tuple[str, ...] = ()
            return
        if self.descendant:
            path = path[3:]
        elif path.startswith("./"):
            path = path[2:]
        tokens = re.findall(r"\{[^}]*\}[^/]*|[^/]+", path)
        if not tokens or "/".join(tokens) != path:
            raise ValueError(
                "Invalid XML record path; use relative child paths or .//name."
            )
        namespaces = dict(options.namespaces)
        parts: list[str] = []
        for token in tokens:
            if token.startswith("{"):
                _, _, name = token.partition("}")
            elif ":" in token:
                prefix, name = token.split(":", 1)
                if prefix not in namespaces:
                    raise ValueError(
                        f"XML record path uses unknown namespace prefix {prefix!r}."
                    )
                token = "{" + namespaces[prefix] + "}" + name
            else:
                name = token
            if name != "*" and not re.fullmatch(r"[^\s/\[\]@()*{}:]+", name):
                raise ValueError(
                    "Invalid XML record path; supported paths use names, * and .//name."
                )
            if not name:
                raise ValueError("Invalid XML record path: missing element name.")
            parts.append(token)
        self.parts = tuple(parts)

    def matches(self, stack: list[ET.Element]) -> bool:
        depth = len(stack) - 1
        if self.descendant:
            if depth < len(self.parts):
                return False
            elements = stack[len(stack) - len(self.parts) :]
        else:
            if depth != len(self.parts):
                return False
            elements = stack[1:]
        return all(
            part == "*"
            or part == element.tag
            or (part.endswith("}*") and element.tag.startswith(part[:-1]))
            for part, element in zip(self.parts, elements, strict=True)
        )


def selected_records(source: BinaryIO, path: RecordPath) -> Iterator[ET.Element]:
    stack: list[ET.Element] = []
    record_depth: int | None = None
    try:
        for event, element in ET.iterparse(source, events=("start", "end")):
            if event == "start":
                stack.append(element)
                if record_depth is None and path.matches(stack):
                    record_depth = len(stack)
            else:
                if record_depth == len(stack):
                    yield element
                    record_depth = None
                if record_depth is None:
                    if len(stack) > 1:
                        stack[-2].remove(element)
                    element.clear()
                stack.pop()
    except ET.ParseError as error:
        raise ValueError(f"Malformed XML: {error}") from error
