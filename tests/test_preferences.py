"""Preference round trips and independently recoverable old/corrupt settings."""

import json
from pathlib import Path

import pytest

from datelier.inspection.exploration import PlotSettings
from datelier.plotting.distributions import DistributionSettings
from datelier.workspace.preferences import (
    Preferences,
    Theme,
    preference_path,
    read_preferences,
    save_preferences,
)
from datelier.workspace.types import WorkspaceViews

LAYOUT = (
    "[Window][Table preview]\nPos=0,0\nSize=800,600\n"
    "[Docking][Data]\nDockSpace ID=0x1 Pos=0,0 Size=800,600\n"
)


def test_preferences_round_trip_and_default_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = preference_path()
    preferences = Preferences(
        Theme.LIGHT,
        LAYOUT,
        PlotSettings(
            bins=9,
            scatter_pair=("x", "y"),
            comparison=DistributionSettings(("y", "x"), True, False, 2, 12),
        ),
        WorkspaceViews("Scatter", 2, 1, 0, 1, 16, 100),
        ("Context",),
    )
    save_preferences(path, preferences)
    loaded, message = read_preferences(path)
    assert loaded == preferences and message == "Preferences restored."
    assert path == tmp_path / "datelier" / "preferences.json"


@pytest.mark.parametrize(
    "content", ["{", "[]", '{"version":3}', '{"version":true}', '"wrong"']
)
def test_bad_or_unsupported_file_uses_defaults(tmp_path: Path, content: str) -> None:
    path = tmp_path / "preferences.json"
    path.write_text(content)
    preferences, message = read_preferences(path)
    assert preferences == Preferences() and "reset" in message


def test_missing_optional_preferences_use_defaults(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    assert read_preferences(path)[0] == Preferences()
    path.write_text('{"version":1,"theme":"Classic"}')
    assert read_preferences(path)[0] == Preferences(theme=Theme.CLASSIC)


@pytest.mark.parametrize(
    "edit,note",
    [
        ({"layout_version": 3}, "layout"),
        ({"layout": "unusable"}, "layout"),
        ({"theme": "missing"}, "theme"),
        ({"plots": {"kind": "PlotSettings", "bins": 0}}, "plot"),
        (
            {"plots": {"kind": "PlotSettings", "relationship_features": ["x", "x"]}},
            "plot",
        ),
        ({"views": {"kind": "WorkspaceViews", "tab": "missing"}}, "views"),
    ],
)
def test_invalid_section_retains_other_valid_sections(
    tmp_path: Path, edit: dict[str, object], note: str
) -> None:
    path = tmp_path / "preferences.json"
    initial = Preferences(
        Theme.LIGHT, LAYOUT, PlotSettings(bins=9), WorkspaceViews("Scatter")
    )
    save_preferences(path, initial)
    raw = json.loads(path.read_text())
    raw.update(edit)
    path.write_text(json.dumps(raw))
    preferences, message = read_preferences(path)
    assert note in message.lower()
    if note != "theme":
        assert preferences.theme == Theme.LIGHT
    if note != "layout":
        assert preferences.layout == LAYOUT
    if note != "plot":
        assert preferences.plots.bins == 9
    if note != "views":
        assert preferences.views.tab == "Scatter"


def test_preference_save_protects_source_and_previous_file(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    save_preferences(path, Preferences())
    before = path.read_bytes()
    with pytest.raises(ValueError, match="layout"):
        save_preferences(path, Preferences(layout="bad"))
    assert path.read_bytes() == before
    source = tmp_path / "data.csv"
    source.write_text("x\n1\n")
    alias = tmp_path / "alias.json"
    alias.symlink_to(source)
    with pytest.raises(ValueError, match="source data"):
        save_preferences(alias, Preferences(), sources=(source,))
    assert source.read_text() == "x\n1\n"


def test_invalid_layout_unicode_recovers_without_losing_theme(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({"version": 1, "theme": "Light", "layout": "\ud800"}))
    preferences, message = read_preferences(path)
    assert preferences.theme == Theme.LIGHT and preferences.layout == ""
    assert "layout reset" in message


def test_version_one_preferences_keep_theme_recipes_and_clear_legacy_docking(
    tmp_path: Path,
) -> None:
    path = tmp_path / "preferences.json"
    settings = Preferences(
        Theme.LIGHT,
        LAYOUT,
        PlotSettings(bins=17),
        WorkspaceViews(profile_selection=("x", "y"), target_row=42),
        ("Analysis",),
    )
    save_preferences(path, settings)
    raw = json.loads(path.read_text())
    raw.update(version=1, layout_version=1)
    path.write_text(json.dumps(raw))
    loaded, notice = read_preferences(path)
    assert loaded.theme == Theme.LIGHT and loaded.plots.bins == 17
    assert loaded.views == settings.views
    assert loaded.layout == "" and loaded.hidden_windows == ()
    assert "Workbench layout updated" in notice
