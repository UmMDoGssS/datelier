"""Common file/view source chooser; each source has an independent field mapping."""

from collections.abc import Callable

from datelier.application.comparisons.catalog import ComparisonFile, SourceCatalog
from datelier.application.tabular import ColumnChoice, MultiSelection
from datelier.gui.components.base import Component, Container, FrameContext
from datelier.gui.components.columns import ColumnPicker


class ContributorControls(Container):
    def __init__(
        self,
        catalog: SourceCatalog,
        selected: Callable[[], tuple[str, ...]],
        choose: Callable[[tuple[str, ...]], None],
        form: Callable[[ComparisonFile], Component],
    ) -> None:
        super().__init__(
            "contributors",
            (
                ColumnPicker(
                    "files",
                    "Contributing files and views",
                    lambda: tuple(
                        ColumnChoice(
                            f.identity,
                            "Named record views" if f.view_name else "Files",
                            enabled=f.dataset is not None,
                            reason="Open or recover this source first.",
                            label=f.title,
                        )
                        for f in catalog.files
                    ),
                    selected,
                    choose,
                    MultiSelection(limit=32),
                ),
            ),
        )
        self.catalog, self.selected, self.form = catalog, selected, form
        self.picker = self.children[0]
        self.forms: dict[str, Component] = {}

    def render(self, frame: FrameContext) -> None:
        for identity in set(self.forms) - set(self.catalog.by_id):
            self.forms.pop(identity).close()
        for identity in self.selected():
            source = self.catalog.by_id.get(identity)
            if source and identity not in self.forms:
                self.forms[identity] = self.form(source)
        self.children = (
            self.picker,
            *(self.forms[key] for key in self.selected() if key in self.forms),
        )
        super().render(frame)

    def close(self) -> None:
        for form in self.forms.values():
            form.close()
        self.forms.clear()
        self.children = ()
