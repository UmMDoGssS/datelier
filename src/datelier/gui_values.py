"""Scalar input decoding shared by edit controls."""

import json

from datelier.scalars import Scalar


def scalar_input(text: str) -> Scalar:
    try:
        value = json.loads(text)
    except ValueError:
        return text
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("Use a number, boolean, null, or text value")
