"""Display-only table styles with atomic custom-range drafts."""

from dataclasses import replace

from datelier.inspection.presentation import TablePresentation


class PresentationController:
    def __init__(self) -> None:
        self.settings = TablePresentation()
        self.minimum, self.maximum = 0.0, 1.0

    def restore(self, settings: TablePresentation) -> None:
        settings.validate()
        self.settings = settings
        self.minimum, self.maximum = settings.minimum, settings.maximum

    def apply(self) -> None:
        settings = replace(self.settings, minimum=self.minimum, maximum=self.maximum)
        settings.validate()
        self.settings = settings
