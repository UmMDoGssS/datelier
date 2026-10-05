"""Trusted numeric/choice metadata shared by concrete method settings."""

from dataclasses import field


def setting[T](default: T, label: str, minimum: float = 0, maximum: float = 1e6) -> T:
    return field(
        default=default, metadata={"label": label, "min": minimum, "max": maximum}
    )


def choice(default: str, label: str, values: tuple[str, ...]) -> str:
    return field(default=default, metadata={"label": label, "choices": values})
