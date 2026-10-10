"""Prepared text statistics, bounded plots and complete virtual frequency rows."""

from dataclasses import dataclass

from imgui_bundle import imgui, implot

from datelier.gui.text.statistics import number, statistics
from datelier.inspection.text.profiles import PreparedTextProfile
from datelier.inspection.text.statistics import TextProfile


@dataclass
class TextProfiles:
    plot_frames: int = 0
    rendered_frequency_rows: int = 0
    shown: int = 0

    def show(self, data: PreparedTextProfile) -> None:
        self.shown += 1
        profile = data.profile
        imgui.text_wrapped(
            f"Exact corpus · {profile.settings.column} · {profile.settings.scope.mode}"
        )
        if profile.settings.scope.mode.value in ("Row range", "Seeded random sample"):
            imgui.text_wrapped(
                f"Start {profile.settings.scope.start} · "
                f"requested {profile.settings.scope.count:,} · "
                f"seed {profile.settings.scope.seed}"
            )
        if imgui.begin_tab_bar("Text profile views"):
            if imgui.begin_tab_item("Statistics")[0]:
                statistics(profile)
                imgui.end_tab_item()
            if imgui.begin_tab_item("Length distribution")[0]:
                if implot.begin_plot("Corpus token lengths", (-1, 260)):
                    implot.setup_axes(
                        "Counted tokens per document", "Decoded documents"
                    )
                    implot.plot_bars(
                        "Documents",
                        data.length_centers,
                        data.length_counts,
                        bar_size=data.length_width * 0.9,
                    )
                    implot.end_plot()
                    self.plot_frames += 1
                imgui.end_tab_item()
            if imgui.begin_tab_item("Token frequencies")[0]:
                imgui.text_wrapped(
                    f"Chart: first {len(data.frequency_labels):,} of "
                    f"{profile.vocabulary_size:,} types, ordered by token count. "
                    "Complete exact rows below; token/document counts differ."
                )
                if data.frequency_labels and implot.begin_plot(
                    "Top token frequencies", (-1, 300)
                ):
                    implot.setup_axes(
                        "Frequency", "Token piece", y_flags=implot.AxisFlags_.invert
                    )
                    implot.setup_axis_ticks(
                        implot.ImAxis_.y1,
                        data.frequency_positions.tolist(),
                        list(data.frequency_labels),
                    )
                    implot.plot_bars(
                        "Token count",
                        data.frequency_tokens,
                        data.frequency_positions,
                        bar_size=0.7,
                        spec=implot.Spec(flags=implot.BarsFlags_.horizontal),
                    )
                    implot.plot_bars(
                        "Document count",
                        data.frequency_documents,
                        data.frequency_positions,
                        bar_size=0.3,
                        spec=implot.Spec(flags=implot.BarsFlags_.horizontal),
                    )
                    implot.end_plot()
                    self.plot_frames += 1
                self._frequencies(profile)
                imgui.end_tab_item()
            if imgui.begin_tab_item("Record outcomes")[0]:
                self._records(profile)
                imgui.end_tab_item()
            imgui.end_tab_bar()

    def _frequencies(self, profile: TextProfile) -> None:
        flags = (
            imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
        )
        self.rendered_frequency_rows = 0
        if imgui.begin_table("Complete token frequencies", 4, flags, (-1, 200)):
            for label in ("Piece", "ID", "Tokens", "Documents"):
                imgui.table_setup_column(label)
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(profile.frequencies.height)
            while clipper.step():
                for row in range(clipper.display_start, clipper.display_end):
                    self.rendered_frequency_rows += 1
                    imgui.table_next_row()
                    values = profile.frequencies.row(row)
                    for column, value in enumerate(values):
                        imgui.table_next_column()
                        imgui.text_unformatted(
                            repr(value)[:256]
                            if column == 0
                            else "—"
                            if column == 1 and value is None
                            else number(value)
                        )
            imgui.end_table()

    def _records(self, profile: TextProfile) -> None:
        flags = (
            imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
        )
        if imgui.begin_table("Complete record outcomes", 4, flags, (-1, 280)):
            for label in ("Source row", "Status", "Token length", "Diagnostic"):
                imgui.table_setup_column(label)
            imgui.table_headers_row()
            clipper = imgui.ListClipper()
            clipper.begin(profile.records.height)
            while clipper.step():
                for row in range(clipper.display_start, clipper.display_end):
                    values = profile.records.row(row)
                    imgui.table_next_row()
                    for column, value in enumerate(
                        (values[0], values[1], values[2], values[5])
                    ):
                        imgui.table_next_column()
                        imgui.text_unformatted(
                            number(value) if column in (0, 2) else str(value)[:256]
                        )
            imgui.end_table()
