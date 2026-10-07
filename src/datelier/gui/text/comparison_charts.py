"""Native prepared length/frequency overlays and complete virtual tables."""

from imgui_bundle import imgui, implot

from datelier.gui.text.profiles import statistics
from datelier.inspection.text.comparisons.settings import TextScale
from datelier.inspection.text.comparisons.types import PreparedTextComparison
from datelier.inspection.text.types import CorpusMode


def length_chart(result: PreparedTextComparison, fit: bool) -> bool:
    if fit:
        implot.set_next_axes_to_fit()
    if not implot.begin_plot("Shared token lengths", (-1, 240)):
        return False
    implot.setup_axes(
        "Counted tokens per document",
        "Document density"
        if result.settings.scale == TextScale.DENSITY
        else "Decoded documents",
    )
    for label, counts in zip(result.labels, result.lengths, strict=True):
        implot.plot_line(label, result.centers, counts)
    implot.end_plot()
    imgui.text_wrapped(
        "All sources use the same bin edges; lines connect bin centers. "
        "Null/failed records are excluded, empty documents included."
    )
    return True


def frequency_chart(result: PreparedTextComparison, documents: bool, fit: bool) -> bool:
    imgui.text_wrapped(
        f"Chart: first {len(result.frequency_labels)} of "
        f"{result.frequencies.height:,} shared vocabulary types, "
        "ordered by combined token count. Complete raw counts below."
    )
    if fit:
        implot.set_next_axes_to_fit()
    if not result.frequency_labels or not implot.begin_plot(
        "Shared token frequencies", (-1, 300)
    ):
        return False
    proportional = result.settings.scale == TextScale.DENSITY
    implot.setup_axes(
        "Document proportion"
        if proportional and documents
        else "Token proportion"
        if proportional
        else "Document count"
        if documents
        else "Token count",
        "Token piece",
        y_flags=implot.AxisFlags_.invert,
    )
    implot.setup_axis_ticks(
        implot.ImAxis_.y1,
        result.frequency_positions.tolist(),
        list(result.frequency_labels),
    )
    values = result.document_frequencies if documents else result.token_frequencies
    for label, counts, positions in zip(
        result.labels, values, result.frequency_series_positions, strict=True
    ):
        implot.plot_bars(
            label,
            counts,
            positions,
            bar_size=0.8 / len(result.labels),
            spec=implot.Spec(flags=implot.BarsFlags_.horizontal),
        )
    implot.end_plot()
    return True


def frequency_table(result: PreparedTextComparison, documents: bool) -> int:
    flags = (
        imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.scroll_x
        | imgui.TableFlags_.borders
        | imgui.TableFlags_.row_bg
        | imgui.TableFlags_.sizing_fixed_fit
    )
    rendered = 0
    keys = (
        "piece",
        "token_id",
        *(
            f"{'documents' if documents else 'tokens'}_{i}"
            for i in range(len(result.labels))
        ),
    )
    if imgui.begin_table("Complete shared vocabulary", len(keys), flags, (-1, 200)):
        for label in ("Piece", "ID", *result.labels):
            imgui.table_setup_column(label, init_width_or_weight=140)
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(result.frequencies.height)
        while clipper.step():
            for row in range(clipper.display_start, clipper.display_end):
                rendered += 1
                imgui.table_next_row()
                for col, key in enumerate(keys):
                    value = result.frequencies[key][row]
                    imgui.table_next_column()
                    imgui.text_unformatted(
                        repr(value)[:256]
                        if col == 0
                        else "—"
                        if value is None
                        else f"{value:,}"
                    )
        imgui.end_table()
    return rendered


def statistics_table(result: PreparedTextComparison) -> None:
    flags = (
        imgui.TableFlags_.scroll_x
        | imgui.TableFlags_.borders
        | imgui.TableFlags_.sizing_fixed_fit
    )
    if imgui.begin_table("Text statistics by source", len(result.profiles), flags):
        for label in result.labels:
            imgui.table_setup_column(label, init_width_or_weight=340)
        imgui.table_headers_row()
        imgui.table_next_row()
        for profile in result.profiles:
            imgui.table_next_column()
            scope = profile.settings.scope
            details = (
                f" · start {scope.start} · count {scope.count:,}"
                if scope.mode == CorpusMode.RANGE
                else f" · count {scope.count:,} · seed {scope.seed}"
                if scope.mode == CorpusMode.RANDOM
                else ""
            )
            imgui.text_wrapped(
                f"Field {profile.settings.column} · scope {scope.mode}{details}"
            )
            statistics(profile)
        imgui.end_table()
