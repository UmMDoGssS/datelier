"""Typed constructor bindings for fields over immutable feature settings."""

from collections.abc import Callable

from datelier.gui.components.inputs.fields import (
    BooleanField,
    ChoiceField,
    FloatField,
    IntegerField,
    TextField,
)


class StateFields[T]:
    def __init__(self, read: Callable[[], T], write: Callable[[T], None]) -> None:
        self.read, self.write = read, write

    def integer(
        self,
        key: str,
        label: str,
        get: Callable[[T], int],
        update: Callable[[T, int], T],
        minimum: int = 0,
        maximum: int = 2**31 - 1,
    ) -> IntegerField:
        return IntegerField(
            key,
            label,
            lambda: get(self.read()),
            lambda value: self.write(update(self.read(), value)),
            minimum,
            maximum,
        )

    def floating(
        self,
        key: str,
        label: str,
        get: Callable[[T], float],
        update: Callable[[T, float], T],
        minimum: float = 0,
        maximum: float = 1e9,
    ) -> FloatField:
        return FloatField(
            key,
            label,
            lambda: get(self.read()),
            lambda value: self.write(update(self.read(), value)),
            minimum,
            maximum,
        )

    def choice[V](
        self,
        key: str,
        label: str,
        choices: tuple[V, ...] | Callable[[], tuple[V, ...]],
        get: Callable[[T], V],
        update: Callable[[T, V], T],
    ) -> ChoiceField[V]:
        return ChoiceField(
            key,
            label,
            choices,
            lambda: get(self.read()),
            lambda value: self.write(update(self.read(), value)),
        )

    def boolean(
        self,
        key: str,
        label: str,
        get: Callable[[T], bool],
        update: Callable[[T, bool], T],
    ) -> BooleanField:
        return BooleanField(
            key,
            label,
            lambda: get(self.read()),
            lambda value: self.write(update(self.read(), value)),
        )

    def text(
        self,
        key: str,
        label: str,
        get: Callable[[T], str],
        update: Callable[[T, str], T],
        *,
        multiline: bool = False,
    ) -> TextField:
        return TextField(
            key,
            label,
            lambda: get(self.read()),
            lambda value: self.write(update(self.read(), value)),
            multiline,
        )
