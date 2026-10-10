"""Tables for exact corpus totals and per-document length statistics."""

from collections.abc import Sequence

from imgui_bundle import imgui

from datelier.inspection.text.statistics import TextProfile


def number(value: int | float | None) -> str:
    return (
        "undefined"
        if value is None
        else f"{value:,}"
        if isinstance(value, int)
        else f"{value:.6g}"
    )


def _table(
    title: str, headings: Sequence[str], rows: Sequence[Sequence[str]], height: float
) -> None:
    imgui.separator_text(title)
    flags = (
        imgui.TableFlags_.borders
        | imgui.TableFlags_.row_bg
        | imgui.TableFlags_.scroll_x
        | imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.resizable
        | imgui.TableFlags_.sizing_fixed_fit
    )
    if not imgui.begin_table(title, len(headings), flags, (-1, height)):
        return
    for heading in headings:
        imgui.table_setup_column(heading)
    imgui.table_setup_scroll_freeze(1, 1)
    imgui.table_headers_row()
    for row in rows:
        imgui.table_next_row()
        for value in row:
            imgui.table_next_column()
            imgui.text_unformatted(value)
    imgui.end_table()


def statistics(profile: TextProfile) -> None:
    totals = (
        (
            "Requested rows" if profile.is_list else "Requested records",
            profile.requested_records,
        ),
        (
            "Decoded text elements" if profile.is_list else "Decoded documents",
            profile.documents,
        ),
        (
            "Empty text elements" if profile.is_list else "Empty documents",
            profile.empty,
        ),
        ("Null elements" if profile.is_list else "Null records", profile.nulls),
        (
            "Failed text elements" if profile.is_list else "Failed records",
            profile.failures,
        ),
        ("Counted tokens", profile.tokens),
        ("Vocabulary types", profile.vocabulary_size),
        ("Original code points", profile.original_code_points),
        ("Normalized code points", profile.normalized_code_points),
        ("Inserted special tokens", profile.special_tokens),
        ("Counted special tokens", profile.counted_special_tokens),
        ("Hapax", profile.hapax),
        ("Hapax / vocabulary", profile.hapax_vocabulary_ratio),
        ("Hapax / tokens", profile.hapax_token_ratio),
        ("Type-token ratio", profile.type_token_ratio),
        ("Shannon entropy (bits)", profile.entropy_bits),
    )
    _table(
        "Corpus statistics",
        ("Statistic", "Value"),
        tuple((label, number(value)) for label, value in totals),
        210,
    )
    headings = (
        "Length",
        "Elements" if profile.is_list else "Documents",
        "Mean",
        "Std (population)",
        "Min",
        "25%",
        "50%",
        "75%",
        "95%",
        "99%",
        "Max",
    )
    rows = []
    for label, lengths in (
        ("Tokens", profile.token_lengths),
        ("Original code points", profile.character_lengths),
    ):
        quantiles = dict(lengths.quantiles)
        rows.append(
            (
                label,
                *map(
                    number,
                    (
                        lengths.count,
                        lengths.mean,
                        lengths.stddev,
                        lengths.minimum,
                        quantiles.get(0.25),
                        lengths.median,
                        quantiles.get(0.75),
                        quantiles.get(0.95),
                        quantiles.get(0.99),
                        lengths.maximum,
                    ),
                ),
            )
        )
    _table(
        "Element length statistics"
        if profile.is_list
        else "Document length statistics",
        headings,
        rows,
        110,
    )
    imgui.text_wrapped(
        (
            "Null/failed elements are excluded from length statistics; empty text "
            "elements are included. "
            if profile.is_list
            else "Null/failed records are excluded from length statistics; empty "
            "documents are included. "
        )
        + "Standard deviation uses the population; quantiles use linear interpolation."
    )
