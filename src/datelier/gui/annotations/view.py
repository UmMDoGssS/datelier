"""Explicit source commands and prepared image outcomes in Inspect."""

from dataclasses import replace
from typing import TYPE_CHECKING
from uuid import uuid4

from imgui_bundle import imgui

from datelier.gui.annotations.outcomes import outcomes
from datelier.gui.annotations.profiles import AnnotationProfilesView
from datelier.gui.annotations.source_controls import SourceControls
from datelier.inspection.annotations.settings import (
    AnnotationSettings,
    AnnotationSource,
)

if TYPE_CHECKING:
    from datelier.gui.file_session import FileSession


class AnnotationView:
    def __init__(self) -> None:
        self.sources: dict[str, SourceControls] = {}
        self.active_tab = "Sources"
        self.shown = 0
        self.profiles = AnnotationProfilesView()
        self._observed_tab: str | None = None

    def show(self, owner: FileSession, column: str) -> None:
        if not imgui.collapsing_header("Detection annotations"):
            return
        self.shown += 1
        view = owner.images
        settings = view.settings.annotations
        view_state = view.settings.annotation_view
        requested = view_state.tab if self._observed_tab != view_state.tab else ""
        if settings.column is None:
            settings = replace(settings, column=column)
        active = owner.loader.active
        columns = tuple(active.dataset.table.columns) if active else ()
        if settings.column not in columns:
            imgui.text_unformatted(f"Image field: {settings.column}")
        else:
            _, choice = imgui.combo(
                "Annotation image field", columns.index(settings.column), list(columns)
            )
            settings = replace(settings, column=columns[choice])
        if imgui.begin_tab_bar("Annotation inspection"):
            if imgui.begin_tab_item(
                "Sources",
                flags=imgui.TabItemFlags_.set_selected if requested == "Sources" else 0,
            )[0]:
                self.active_tab = "Sources"
                view_state = replace(view_state, tab="Sources")
                settings = self._sources(settings, columns)
                imgui.end_tab_item()
            if imgui.begin_tab_item(
                "Associations",
                flags=imgui.TabItemFlags_.set_selected
                if requested == "Associations"
                else 0,
            )[0]:
                self.active_tab = "Associations"
                view_state = replace(view_state, tab="Associations")
                prepared = view.annotations.active
                if prepared is not None:
                    if imgui.begin_child(
                        "Annotation associations", (0, 280), imgui.ChildFlags_.borders
                    ):
                        for source in prepared.sources:
                            imgui.push_id(source.recipe.id)
                            if imgui.collapsing_header(
                                source.recipe.name or source.recipe.path,
                                imgui.TreeNodeFlags_.default_open,
                            ):
                                outcomes(source, prepared, owner)
                            imgui.pop_id()
                    imgui.end_child()
                else:
                    imgui.text(
                        "Load sources to inspect image keys, candidate rows and issues."
                    )
                imgui.end_tab_item()
            if imgui.begin_tab_item(
                "Profiles",
                flags=imgui.TabItemFlags_.set_selected
                if requested == "Profiles"
                else 0,
            )[0]:
                self.active_tab = "Profiles"
                view_state = self.profiles.show(
                    owner, replace(view_state, tab="Profiles")
                )
                imgui.end_tab_item()
            imgui.end_tab_bar()
        self._observed_tab = view_state.tab
        view.settings = replace(
            view.settings, annotations=settings, annotation_view=view_state
        )
        view.sync(owner)
        if imgui.button("Load / associate annotations"):
            try:
                view.annotations.request()
            except ValueError as error:
                view.annotations.message = str(error)
        if view.annotations.busy:
            imgui.same_line()
            if imgui.button("Abandon annotation loading"):
                view.annotations.abandon()
                view.annotations.message = (
                    "Loading abandoned; executing reads are winding down."
                )
            phase, done, total = view.annotations.progress.value
            imgui.text(f"{phase} · {done:,}/{total:,}")
        imgui.text_wrapped(view.annotations.message)

    def _sources(
        self, settings: AnnotationSettings, columns: tuple[str, ...]
    ) -> AnnotationSettings:
        sources = list(settings.sources)
        added: str | None = None
        if imgui.button("Add annotation source"):
            added = str(uuid4())
            sources.append(AnnotationSource(added, ""))
        removed: str | None = None
        for index, source in enumerate(sources):
            imgui.push_id(source.id)
            label = source.name or f"Source {index + 1}"
            if source.id == added:
                imgui.set_next_item_open(True)
            if imgui.tree_node(f"{label}###Annotation source"):
                controls = self.sources.setdefault(source.id, SourceControls())
                sources[index] = controls.show(source, columns)
                if imgui.button("Remove annotation source"):
                    removed = source.id
                imgui.tree_pop()
            imgui.pop_id()
        return replace(
            settings,
            sources=tuple(source for source in sources if source.id != removed),
        )
