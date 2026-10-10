"""Related comparison recipe controllers share identity and draft lifecycle."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum


class ComparisonFamily(StrEnum):
    COLUMNS = "Columns"
    TEXT = "Text"
    IMAGES = "Images"
    AUDIO = "Audio"


@dataclass(frozen=True)
class ComparisonEntry:
    identity: int
    title: str


class RecipeController[Recipe](ABC):
    def __init__(self, default: Recipe) -> None:
        self.recipes: tuple[Recipe, ...] = ()
        self.index = 0
        self.draft = default
        self._default = default
        self.message = ""

    @property
    @abstractmethod
    def family(self) -> ComparisonFamily: ...

    @abstractmethod
    def validate(self, recipe: Recipe) -> None: ...

    @abstractmethod
    def prune(self, identities: set[str]) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @property
    def recipe(self) -> Recipe | None:
        return self.recipes[self.index] if self.recipes else None

    @property
    def changed(self) -> bool:
        return self.draft != (self.recipe or self._default)

    def apply(self) -> None:
        self.validate(self.draft)
        if not self.recipes:
            self.recipes = (self.draft,)
            self.index = 0
        else:
            self.recipes = tuple(
                self.draft if i == self.index else recipe
                for i, recipe in enumerate(self.recipes)
            )

    def choose(self, index: int) -> None:
        if not 0 <= index < len(self.recipes):
            return
        self.index = index
        self.draft = self.recipes[index]

    def new(self) -> None:
        if len(self.recipes) >= 32:
            raise ValueError("Keep at most 32 comparisons per family")
        self.recipes = (*self.recipes, self._default)
        self.choose(len(self.recipes) - 1)

    def remove(self) -> None:
        self.recipes = tuple(
            recipe for i, recipe in enumerate(self.recipes) if i != self.index
        )
        self.index = min(self.index, max(0, len(self.recipes) - 1))
        self.draft = self.recipe or self._default

    def restore(self, recipes: tuple[Recipe, ...], index: int = 0) -> None:
        self.recipes = recipes
        self.index = min(index, max(0, len(recipes) - 1))
        self.draft = self.recipe or self._default
