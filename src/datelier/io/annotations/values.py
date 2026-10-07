"""Narrow JSON/YAML schema values without coercing identifiers or coordinates."""

from math import isfinite


def mapping(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{context} requires an object with named fields")
    return {key: item for key, item in value.items()}


def sequence(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{context} requires an array")
    return list(value)


def integer(value: object, context: str, *, positive: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < int(positive):
        raise ValueError(
            f"{context} requires "
            f"{'positive' if positive else 'nonnegative'} integer values"
        )
    return value


def text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} requires nonempty text")
    return value


def number(value: object, context: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{context} requires finite numeric values")
    try:
        numeric = float(value)
    except OverflowError as error:
        raise ValueError(f"{context} exceeds finite numeric range") from error
    if not isfinite(numeric):
        raise ValueError(f"{context} requires finite numeric values")
    return numeric
