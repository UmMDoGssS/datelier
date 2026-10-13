"""Wide statistics tables prepared once alongside worker-owned profiles."""

from dataclasses import dataclass, fields

from datelier.inspection.profiles.prepare import Profiles


@dataclass(frozen=True)
class ProfileTable:
    key: str
    title: str
    headers: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]


def _label(name: str) -> str:
    return {
        "nonnull": "Non-null",
        "uniques": "Unique",
        "nulls": "Null",
        "nans": "NaN",
        "nonfinites": "Nonfinite",
    }.get(name, name.replace("_", " ").capitalize())


def prepare_statistics_tables(profiles: Profiles) -> tuple[ProfileTable, ...]:
    summary: list[dict[str, object]] = []
    structures: list[tuple[object, ...]] = []
    lengths: list[tuple[object, ...]] = []
    shapes: list[tuple[object, ...]] = []
    length_headers: tuple[str, ...] = ()
    for profile in profiles.columns:
        row: dict[str, object] = {"Column": profile.name}
        if profile.statistics is not None:
            row.update(
                (_label(field.name), getattr(profile.statistics, field.name))
                for field in fields(profile.statistics)
            )
        else:
            row.update(
                {
                    "Non-null": profile.nonnull_count,
                    "Unique": profile.unique_count,
                    "Null": profile.null_count,
                    "Nonfinite": profile.nonfinite_count,
                    "Minimum": profile.minimum,
                    "Maximum": profile.maximum,
                }
            )
        summary.append(row)
        lists = profile.list_statistics
        if lists is None:
            continue
        structures.append(
            (
                profile.name,
                lists.elements,
                lists.null_elements,
                lists.rectangular,
                lists.ragged,
                lists.unknown,
            )
        )
        for dimension in lists.dimensions:
            length_headers = (
                "Column",
                *(_label(field.name) for field in fields(dimension)),
            )
            lengths.append(
                (
                    profile.name,
                    *(getattr(dimension, field.name) for field in fields(dimension)),
                )
            )
        shapes.extend((profile.name, shape, count) for shape, count in lists.shapes)
    headers = tuple(dict.fromkeys(name for row in summary for name in row))
    if "Mean" in headers:
        first = ("Column", "Mean", "Std", "Minimum", "Maximum", "Median")
        headers = (*first, *(name for name in headers if name not in first))
    tables = (
        ProfileTable(
            "statistics",
            "Statistics",
            headers,
            tuple(tuple(row.get(name) for name in headers) for row in summary),
        ),
        ProfileTable(
            "list-structure",
            "List structure",
            ("Column", "Elements", "Null elements", "Rectangular", "Ragged", "Unknown"),
            tuple(structures),
        ),
        ProfileTable("list-lengths", "List lengths", length_headers, tuple(lengths)),
        ProfileTable(
            "list-shapes", "List shapes", ("Column", "Shape", "Count"), tuple(shapes)
        ),
    )
    return tuple(table for table in tables if table.rows)
