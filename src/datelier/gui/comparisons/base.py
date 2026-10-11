"""Comparison content and control families expose one rendering contract."""

from abc import ABC, abstractmethod

from datelier.application.comparisons import ComparisonFamily
from datelier.gui.components.base import Container


class ComparisonContent(Container, ABC):
    @property
    @abstractmethod
    def family(self) -> ComparisonFamily: ...


class ComparisonTools(Container, ABC):
    @property
    @abstractmethod
    def family(self) -> ComparisonFamily: ...
