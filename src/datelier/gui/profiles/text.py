"""Exact text profile tables and plots use prepared arrays and shared viewports."""

from imgui_bundle import imgui, implot

from datelier.application.profiles import ProfileController, ProfileFamily
from datelier.application.text import TextController
from datelier.gui.components.base import FrameContext, Group
from datelier.gui.components.dataframe import DataFrameTable
from datelier.gui.components.facts import FactsTable
from datelier.gui.components.viewport import ResizableViewport, ViewportContent
from datelier.gui.profiles.base import ProfileContent
from datelier.gui.shell.navigation import CanvasTabs, NamedTab


class TextLengthChart(ViewportContent):
    def __init__(self, model: TextController) -> None:
        super().__init__("lengths")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        data = self.model.corpus.profile
        if data is None:
            return
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##lengths", (-1, self.height)):
            implot.setup_axes(
                "Counted tokens per document / text element", "Documents / elements"
            )
            implot.plot_bars(
                "Exact lengths",
                data.length_centers,
                data.length_counts,
                data.length_width * 0.9,
            )
            implot.end_plot()
            self.fit = False


class TokenFrequencyChart(ViewportContent):
    def __init__(self, model: TextController) -> None:
        super().__init__("frequency")
        self.model = model

    def render(self, frame: FrameContext) -> None:
        data = self.model.corpus.profile
        if data is None or not data.frequency_labels:
            return
        imgui.text_wrapped(
            f"Chart shows the first {len(data.frequency_labels)} types; "
            f"the exact table includes all {data.profile.vocabulary_size:,} types."
        )
        if self.fit:
            implot.set_next_axes_to_fit()
        if implot.begin_plot("##frequency", (-1, self.height)):
            implot.setup_axes(
                "Frequency", "Token piece", y_flags=implot.AxisFlags_.invert
            )
            implot.setup_axis_ticks(
                implot.ImAxis_.y1,
                data.frequency_positions.tolist(),
                list(data.frequency_labels),
            )
            spec = implot.Spec(flags=implot.BarsFlags_.horizontal)
            implot.plot_bars(
                "Tokens",
                data.frequency_tokens,
                data.frequency_positions,
                bar_size=0.7,
                spec=spec,
            )
            implot.plot_bars(
                "Documents / elements",
                data.frequency_documents,
                data.frequency_positions,
                bar_size=0.3,
                spec=spec,
            )
            implot.end_plot()
            self.fit = False


class TextProfileContent(ProfileContent):
    @property
    def family(self) -> ProfileFamily:
        return ProfileFamily.TEXT

    def __init__(self, model: TextController, profiles: ProfileController) -> None:
        self.model = model
        self.profiles = profiles

        def viewport(key: str, chart: ViewportContent) -> ResizableViewport:
            return ResizableViewport(
                key,
                chart,
                read_height=lambda: profiles.height,
                write_height=lambda value: setattr(profiles, "height", value),
            )

        super().__init__(
            "text-profile",
            (
                CanvasTabs(
                    (
                        NamedTab(
                            "Statistics",
                            Group(
                                "statistics",
                                (
                                    FactsTable(
                                        "corpus",
                                        ("Statistic", "Value"),
                                        lambda: model.statistics,
                                        210,
                                    ),
                                    FactsTable(
                                        "lengths",
                                        (
                                            "Length",
                                            "Count",
                                            "Mean",
                                            "Std (population)",
                                            "Min",
                                            "25%",
                                            "50%",
                                            "75%",
                                            "95%",
                                            "99%",
                                            "Max",
                                        ),
                                        lambda: model.lengths,
                                        110,
                                    ),
                                ),
                            ),
                        ),
                        NamedTab(
                            "Length distribution",
                            viewport("text-lengths", TextLengthChart(model)),
                        ),
                        NamedTab(
                            "Token frequencies",
                            Group(
                                "frequencies",
                                (
                                    viewport(
                                        "text-frequency", TokenFrequencyChart(model)
                                    ),
                                    DataFrameTable(
                                        "all-frequencies",
                                        lambda: (
                                            model.corpus.profile.profile.frequencies
                                            if model.corpus.profile
                                            else None
                                        ),
                                    ),
                                ),
                            ),
                        ),
                        NamedTab(
                            "Record outcomes",
                            DataFrameTable(
                                "outcomes",
                                lambda: (
                                    model.corpus.profile.profile.records
                                    if model.corpus.profile
                                    else None
                                ),
                                300,
                            ),
                        ),
                    ),
                    lambda: model.profile_tab,
                    lambda name: setattr(model, "profile_tab", name),
                ),
            ),
        )

    def render(self, frame: FrameContext) -> None:
        imgui.text_wrapped(self.model.corpus.message)
        prepared = self.model.corpus.profile
        if prepared:
            profile = prepared.profile
            if (profile.settings.column,) != self.profiles.selected:
                imgui.text_wrapped(
                    "Earlier corpus shown. Calculate uses the chosen column."
                )
            imgui.text_wrapped(
                f"Exact corpus · {profile.settings.column} · "
                f"{profile.settings.scope.mode} · {profile.settings.tokens.mode}"
            )
            imgui.text_wrapped(f"Input SHA-256: {profile.input_sha256}")
            if profile.is_list:
                imgui.text_wrapped(
                    "Each text element is a document. "
                    "Null/empty containers contribute no documents."
                )
            imgui.text_wrapped(
                "Null/failed documents are excluded from lengths. "
                "Empty text is included. "
                "Quantiles use linear interpolation."
            )
            super().render(frame)
