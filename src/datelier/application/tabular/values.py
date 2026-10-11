"""Small trusted scalar/lookup command parsing; no rendering dependencies."""

import json

from datelier.core import Scalar


def scalar_input(text: str) -> Scalar:
    try:
        value: object = json.loads(text)
    except ValueError:
        return text
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("Use a number, boolean, null, or text value")


def lookup_entries(text: str) -> tuple[tuple[Scalar, Scalar], ...]:
    values = json.loads(text)
    if not isinstance(values, list):
        raise ValueError("Use a JSON list of [key, value] pairs")
    result: list[tuple[Scalar, Scalar]] = []
    for pair in values:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Each lookup entry needs a key and value")
        key, value = pair
        if not (key is None or isinstance(key, (str, int, float, bool))) or not (
            value is None or isinstance(value, (str, int, float, bool))
        ):
            raise ValueError("Lookup keys and values must be scalar")
        result.append((key, value))
    return tuple(result)
