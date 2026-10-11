"""Import option families preserve hidden recipe fields and literal list entries."""

from abc import ABC, abstractmethod

from datelier.io.types import ImportOptions


def option[T](value: ImportOptions, expected: type[T]) -> T:
    if not isinstance(value, expected):
        raise ValueError("Import options do not match the selected format")
    return value


def entries(text: str, original: tuple[str, ...]) -> tuple[str, ...]:
    # Unchanged text must retain literal newlines, empty tokens and other saved
    # names that a newline-delimited editor cannot represent unambiguously.
    return original if text == "\n".join(original) else tuple(text.splitlines())


class OptionsDraft(ABC):
    @abstractmethod
    def bind(self, value: ImportOptions) -> None: ...

    @abstractmethod
    def build(self) -> ImportOptions: ...
