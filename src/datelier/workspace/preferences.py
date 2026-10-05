"""Small, versioned user preferences with section-level recovery."""

import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

from datelier.inspection.exploration import PlotSettings
from datelier.workspace.codec import decode_record, encode
from datelier.workspace.layout import valid_layout
from datelier.workspace.recent import MAX_RECENT, RecentSource, remember
from datelier.workspace.storage import (
    MAX_WORKSPACE_BYTES,
    atomic_write,
    protect_sources,
)
from datelier.workspace.types import WorkspaceViews


class Theme(StrEnum):
    DARK = "Dark"
    LIGHT = "Light"
    CLASSIC = "Classic"


@dataclass(frozen=True)
class Preferences:
    theme: Theme = Theme.DARK
    layout: str = ""
    plots: PlotSettings = PlotSettings()
    views: WorkspaceViews = WorkspaceViews()
    hidden_windows: tuple[str, ...] = ()
    recent: tuple[RecentSource, ...] = ()


def preference_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return root / "datelier" / "preferences.json"


def read_preferences(path: Path) -> tuple[Preferences, str]:
    if not path.exists():
        return Preferences(), "Using default preferences."
    try:
        with path.open("rb") as stream:
            content = stream.read(MAX_WORKSPACE_BYTES + 1)
        if len(content) > MAX_WORKSPACE_BYTES:
            raise ValueError("Preferences exceed the 2 MiB limit")
        value = cast(object, json.loads(content))
        if not isinstance(value, dict):
            raise ValueError("Preferences must be an object")
        raw = cast(dict[str, object], value)
        if type(raw.get("version", 1)) is not int or raw.get("version", 1) != 1:
            raise ValueError("Unsupported preferences version")
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        return Preferences(), f"Preferences reset: {error}"
    notes: list[str] = []
    try:
        theme = Theme(raw.get("theme", Theme.DARK))
    except TypeError, ValueError:
        theme = Theme.DARK
        notes.append("Unknown theme reset.")
    layout = raw.get("layout", "")
    if (
        type(raw.get("layout_version", 1)) is not int
        or raw.get("layout_version", 1) != 1
        or not isinstance(layout, str)
        or not valid_layout(layout)
        or "[Window][Open dataset]" in layout
        or "[Window][Workspace]" in layout
    ):
        layout = ""
        notes.append("Outdated or unusable layout reset.")
    plots = PlotSettings()
    if "plots" in raw:
        try:
            candidate = decode_record(PlotSettings, raw["plots"])
            candidate.validate()
            if (
                candidate.clusters is not None
                or len(candidate.relationship_features) > 16
                or len(set(candidate.relationship_features))
                != len(candidate.relationship_features)
            ):
                raise ValueError("Invalid plot preferences")
            plots = candidate
        except ValueError, TypeError:
            notes.append("Invalid plot preferences reset.")
    views = WorkspaceViews()
    if "views" in raw:
        try:
            views = decode_record(WorkspaceViews, raw["views"])
            views.validate()
        except ValueError, TypeError:
            views = WorkspaceViews()
            notes.append("Invalid views reset.")
    hidden = raw.get("hidden_windows", [])
    hidden_windows = (
        tuple(n for n in hidden if isinstance(n, str))
        if isinstance(hidden, list)
        else ()
    )
    recent: tuple[RecentSource, ...] = ()
    entries = raw.get("recent", [])
    if isinstance(entries, list):
        for entry in reversed(entries[:MAX_RECENT]):
            try:
                recent = remember(recent, decode_record(RecentSource, entry))
            except ValueError, TypeError, UnicodeError:
                notes.append("Invalid recent entry skipped.")
    else:
        notes.append("Invalid recent sources reset.")
    return Preferences(theme, layout, plots, views, hidden_windows, recent), " ".join(
        notes
    ) or "Preferences restored."


def save_preferences(
    path: Path, preferences: Preferences, *, sources: tuple[Path, ...] = ()
) -> None:
    path = path.expanduser().resolve()
    protect_sources(path, sources)
    if not valid_layout(preferences.layout):
        raise ValueError("Unusable dock layout")
    preferences.plots.validate()
    preferences.views.validate()
    if preferences.plots.clusters is not None:
        raise ValueError("Preferences cannot contain fitted ML results")
    if len(preferences.recent) > MAX_RECENT:
        raise ValueError("Too many recent sources")
    content = json.dumps(
        {
            "version": 1,
            "theme": preferences.theme.value,
            "layout_version": 1,
            "layout": preferences.layout,
            "plots": encode(preferences.plots),
            "views": encode(preferences.views),
            "hidden_windows": preferences.hidden_windows,
            "recent": encode(preferences.recent),
        },
        indent=2,
        allow_nan=False,
    )
    if len(content.encode("utf8")) > MAX_WORKSPACE_BYTES:
        raise ValueError("Preferences exceed the 2 MiB limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, content + "\n")
