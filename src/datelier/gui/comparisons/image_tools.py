"""Image comparison forms compose shared contributors, scopes and row links."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.application.columns import SingleSelection
from datelier.application.comparisons.base import ComparisonFamily
from datelier.application.comparisons.images import ImageComparisonController
from datelier.gui.comparisons.base import ComparisonTools
from datelier.gui.comparisons.recipe_controls import (
    RecipeControls,
    RowLinkControls,
    SourceCaption,
)
from datelier.gui.comparisons.source_controls import ContributorControls
from datelier.gui.components.actions import JobSnapshot
from datelier.gui.components.base import Container, FrameContext
from datelier.gui.components.bindings import StateFields
from datelier.gui.components.columns import ColumnPicker
from datelier.gui.components.groups import Conditional
from datelier.gui.context.image_sampling import ImageSamplingFields
from datelier.inspection.images.comparisons.settings import ImageComparisonSource


class ImageSourceForm(Container):
    def __init__(self, model: ImageComparisonController, identity: str) -> None:
        self.identity = identity
        fields = StateFields(
            lambda: model.mapping(identity) or ImageComparisonSource(identity),
            model.update_mapping,
        )
        super().__init__(
            identity,
            (
                SourceCaption(model.catalog, identity),
                ColumnPicker(
                    "column",
                    "Mapped image column",
                    lambda: model.catalog.image_choices(identity),
                    lambda: (
                        (column,) if (column := fields.read().profile.column) else ()
                    ),
                    lambda names: fields.write(
                        replace(
                            fields.read(),
                            profile=replace(
                                fields.read().profile,
                                column=next(iter(names), fields.read().profile.column),
                            ),
                        )
                    ),
                    SingleSelection(),
                ),
                ImageSamplingFields(
                    lambda: fields.read().profile,
                    lambda profile: fields.write(
                        replace(fields.read(), profile=profile)
                    ),
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.push_id(self.identity)
        super().render(frame)
        imgui.pop_id()


class ImageComparisonTools(ComparisonTools):
    def __init__(self, model: ImageComparisonController) -> None:
        self.model = model
        fields = StateFields(lambda: model.draft, lambda s: setattr(model, "draft", s))
        view = StateFields(lambda: model.view, lambda s: setattr(model, "view", s))
        super().__init__(
            "image-comparison-tools",
            (
                RecipeControls(
                    model,
                    "Prepare image comparison",
                    model.prepare,
                    lambda: JobSnapshot(
                        model.message,
                        model.jobs.busy,
                        str(model.jobs.progress.value)
                        if model.jobs.busy
                        else model.jobs.selection_message,
                    ),
                    model.jobs.clear,
                ),
                ContributorControls(
                    model.catalog,
                    lambda: tuple(s.file_id for s in model.draft.sources),
                    model.map_files,
                    lambda source: ImageSourceForm(model, source.identity),
                ),
                fields.integer(
                    "bins",
                    "Common histogram bins",
                    lambda s: s.bins,
                    lambda s, v: replace(s, bins=v),
                    1,
                    256,
                ),
                Conditional(
                    "dimensions",
                    lambda: model.view.tab == "Dimensions",
                    (
                        view.choice(
                            "dimension",
                            "Compared dimension",
                            ("Width", "Height", "Aspect ratio"),
                            lambda s: s.dimension,
                            lambda s, v: replace(s, dimension=v),
                        ),
                    ),
                ),
                Conditional(
                    "colors",
                    lambda: model.view.tab == "Colors",
                    (
                        view.choice(
                            "group",
                            "Color family (mode, dtype)",
                            lambda: model.color_groups,
                            lambda s: (s.mode, s.dtype),
                            lambda s, v: replace(s, mode=v[0], dtype=v[1]),
                        ),
                        view.choice(
                            "channel",
                            "Channel",
                            lambda: model.channels,
                            lambda s: s.channel,
                            lambda s, v: replace(s, channel=v),
                        ),
                    ),
                ),
                view.boolean(
                    "proportion",
                    "Compare proportions",
                    lambda s: s.proportions,
                    lambda s, v: replace(s, proportions=v),
                ),
                RowLinkControls(
                    lambda: model.active.labels if model.active else (),
                    lambda: model.view.source,
                    lambda v: view.write(replace(view.read(), source=v)),
                    lambda: model.view.bin_index,
                    lambda v: view.write(replace(view.read(), bin_index=v)),
                    lambda: model.select(
                        model.view.source, model.view.dimension, model.view.bin_index
                    ),
                ),
            ),
        )

    @property
    def family(self) -> ComparisonFamily:
        return ComparisonFamily.IMAGES

    def render(self, frame: FrameContext) -> None:
        if self.model.changed:
            imgui.text_wrapped("Unprepared image comparison changes")
        super().render(frame)
