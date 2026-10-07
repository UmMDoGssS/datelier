"""Virtual prepared record/channel outcomes and adjacent source statistics."""

from collections.abc import Callable, Set

import polars as pl
from imgui_bundle import imgui

from datelier.inspection.audio.comparisons.types import (
    AudioComparisonCurve,
    PreparedAudioComparison,
)

FLAGS = (
    imgui.TableFlags_.borders
    | imgui.TableFlags_.row_bg
    | imgui.TableFlags_.scroll_x
    | imgui.TableFlags_.scroll_y
)


def number(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def statistics(result: PreparedAudioComparison, curve: AudioComparisonCurve) -> None:
    if imgui.begin_table("Compared audio scalar statistics", 5, FLAGS, (-1, 115)):
        for label in ("Source", "Finite records", "Minimum", "Maximum", "Mean"):
            imgui.table_setup_column(
                label,
                imgui.TableColumnFlags_.width_fixed,
                220 if label == "Source" else 120,
            )
        imgui.table_headers_row()
        for label, summary in zip(result.labels, curve.summaries, strict=True):
            imgui.table_next_row()
            cells = (
                (
                    label,
                    *(
                        number(v)
                        for v in (
                            summary.values,
                            summary.minimum,
                            summary.maximum,
                            summary.mean,
                        )
                    ),
                )
                if summary is not None
                else (label, "Unavailable in this unit/channel family", "—", "—", "—")
            )
            for cell in cells:
                imgui.table_next_column()
                imgui.text_unformatted(cell)
        imgui.end_table()


def scalar_table(
    label: str,
    records: pl.DataFrame,
    names: tuple[str, ...],
    labels: tuple[str, ...],
    selected: Set[int] | None = None,
    on_select: Callable[[int], None] | None = None,
) -> int:
    rendered = 0
    if not imgui.begin_table(label, len(names), FLAGS, (-1, 270)):
        return 0
    for title in labels:
        imgui.table_setup_column(
            title,
            imgui.TableColumnFlags_.width_fixed,
            260 if title == "Diagnostic" else 125,
        )
    imgui.table_headers_row()
    indices = tuple(records.columns.index(name) for name in names)
    clipper = imgui.ListClipper()
    clipper.begin(records.height)
    while clipper.step():
        for row in range(clipper.display_start, clipper.display_end):
            rendered += 1
            values = records.row(row)
            imgui.table_next_row()
            for column, index in enumerate(indices):
                imgui.table_next_column()
                if column == 0 and on_select is not None:
                    row_id = int(values[index])
                    if imgui.selectable(
                        f"{row_id}##Audio comparison record",
                        row_id in (selected or set()),
                    )[0]:
                        on_select(row)
                else:
                    value = values[index]
                    if names[column] == "channel" and isinstance(value, int):
                        value += 1
                    imgui.text_unformatted(number(value))
    imgui.end_table()
    return rendered


RECORD_NAMES = (
    "row_id",
    "status",
    "duration",
    "sample_rate",
    "channels",
    "frames",
    "silence_fraction",
    "longest_silence",
    "nonfinite_fraction",
    "diagnostic",
)
RECORD_LABELS = (
    "Source row",
    "Status",
    "Duration (s)",
    "Rate (Hz)",
    "Channels",
    "Frames",
    "Silent frames / all",
    "Longest silence (s)",
    "Nonfinite frames / all",
    "Diagnostic",
)
CHANNEL_NAMES = (
    "row_id",
    "channel",
    "family",
    "minimum",
    "maximum",
    "peak_original",
    "mean",
    "rms",
    "finite",
    "nonfinite",
    "clipped_fraction",
    "silent_fraction",
    "clipping_low",
    "clipping_high",
    "silence_threshold",
    "diagnostic",
)
CHANNEL_LABELS = (
    "Source row",
    "Channel (1-based)",
    "Amplitude units",
    "Original minimum",
    "Original maximum",
    "Original peak",
    "Mean",
    "RMS",
    "Finite samples",
    "Nonfinite samples",
    "Clip / finite",
    "Silent / finite",
    "Clipping low",
    "Clipping high",
    "Silence amplitude",
    "Diagnostic",
)
