"""Category modes, bounded prepared provenance and count routing survive rebuild."""

from pathlib import Path

import pytest
from test_rebuild_comparisons import until

from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.core.column_roles import ColumnRole
from datelier.pipeline.operations import SetColumnRole, Sort
from datelier.plotting.categories import CategoryRepresentation
from datelier.workspace.sessions.jobs import save_snapshot


def test_all_category_relationship_modes_original_rows_and_profile_routing(
    tmp_path: Path,
) -> None:
    source = tmp_path / "pairs.csv"
    source.write_text("kind,group,value\na,x,1.0\na,y,3.0\nb,x,2.0\nb,y,4.0\n")
    original = source.read_bytes()
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(
            editor,
            lambda: file.inspection is not None and file.explorer.active is not None,
        )
        file.editor.request(Sort(("value",), True))
        until(editor, lambda: not file.editor.busy and file.explorer.active is not None)
        for mode in (
            CategoryRepresentation.GROUPED,
            CategoryRepresentation.MEAN,
            CategoryRepresentation.MEDIAN,
            CategoryRepresentation.SUM,
            CategoryRepresentation.BOX,
            CategoryRepresentation.VIOLIN,
        ):
            editor.choose_relationship_chart(mode.value)
            until(
                editor,
                lambda mode=mode: (
                    file.explorer.active is not None
                    and file.explorer.active.category_chart is not None
                    and file.explorer.active.category_chart.settings.representation
                    == mode
                ),
            )
            chart = (
                file.explorer.active.category_chart if file.explorer.active else None
            )
            assert chart
            assert (
                chart.included_rows == chart.total_rows == 4
                and chart.excluded_values == 0
            )
            if mode != CategoryRepresentation.GROUPED:
                assert (
                    chart.row_ids[0][0] == (1, 0) and chart.first_positions[0][0] == 1
                )
                assert chart.value_label
            if mode in (CategoryRepresentation.BOX, CategoryRepresentation.VIOLIN):
                assert len(chart.distributions) == 2 and chart.distributions[0].box
            assert file.views.tab == "Relationships" and not file.analysis.jobs.results
        editor.choose_relationship_chart("Count bars")
        assert file.views.tab == "Profiles" and file.profiles.selected == ("kind",)
        editor.choose_relationship_chart("Grouped count bars")
        file.plots.choose_category("group")
        assert file.plots.category_group == "kind"
        until(
            editor,
            lambda: (
                file.explorer.active is not None
                and file.explorer.active.category_chart is not None
                and file.explorer.active.category_chart.settings.category == "group"
            ),
        )
        file.editor.request(SetColumnRole("kind", ColumnRole.IDENTIFIER))
        until(
            editor,
            lambda: not file.editor.busy and file.plots.relationship_chart == "Scatter",
        )
        assert "Grouped count bars" not in file.plots.chart_choices
        assert source.read_bytes() == original
    finally:
        editor.close()


@pytest.mark.parametrize(
    "mode", [CategoryRepresentation.VIOLIN, CategoryRepresentation.MEAN]
)
def test_category_recipe_reopens_with_independent_height_and_no_analysis(
    tmp_path: Path,
    mode: CategoryRepresentation,
) -> None:
    from dataclasses import replace

    source = tmp_path / "pairs.csv"
    source.write_text("kind,value\na,1.0\na,3.0\nb,2.0\nb,4.0\n")
    workspace = tmp_path / "workspace.json"
    editor = EditorController()
    try:
        file = editor.active
        file.open(source)
        until(editor, lambda: file.inspection is not None)
        editor.choose_relationship_chart(mode.value)
        file.plots.bandwidth = 0.8
        file.plots.seed = 7
        file.views = replace(file.views, scatter_height=250, category_height=360)
        until(
            editor,
            lambda: (
                file.explorer.active is not None
                and file.explorer.active.category_chart is not None
            ),
        )
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(workspace)
        until(
            reopened,
            lambda: (
                not reopened.workspace.busy
                and reopened.current.explorer.active is not None
            ),
        )
        file = reopened.current
        chart = file.explorer.active.category_chart if file.explorer.active else None
        assert chart and chart.settings.representation == mode
        assert chart.settings.bandwidth == 0.8 and chart.settings.seed == 7
        assert file.views.category_height == 360 and file.views.scatter_height == 250
        assert not file.analysis.jobs.results and not reopened.playback.snapshot.request
    finally:
        reopened.close()


def test_legacy_count_workspace_opens_profiles_without_redirecting_inspect(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    from datelier.inspection.exploration import PlotSettings
    from datelier.plotting.categories import CategorySettings
    from datelier.workspace.sessions.storage import (
        read_session_workspace,
        save_session_workspace,
    )

    source = tmp_path / "counts.csv"
    source.write_text("kind,value\na,1.0\na,3.0\nb,2.0\nb,4.0\n")
    workspace = tmp_path / "legacy-counts.json"
    editor = EditorController()
    try:
        editor.active.open(source)
        until(editor, lambda: editor.active.inspection is not None)
        editor.choose_route("Relationships")
        save_snapshot(workspace, capture_session(editor), False)
    finally:
        editor.close()
    session = read_session_workspace(workspace)
    file = session.files[0]
    assert file.recipe
    recipe = replace(
        file.recipe, plots=PlotSettings(category_chart=CategorySettings("kind"))
    )
    for tab, expected in (("Relationships", "Profiles"), ("Inspect", "Inspect")):
        restored_file = replace(
            file, recipe=replace(recipe, views=replace(recipe.views, tab=tab))
        )
        save_session_workspace(workspace, replace(session, files=(restored_file,)))
        reopened = EditorController()
        try:
            reopened.open_workspace(workspace)
            until(reopened, lambda reopened=reopened: not reopened.workspace.busy)
            assert reopened.current.views.tab == expected
            if expected == "Profiles":
                assert reopened.current.profiles.selected == ("kind",)
            assert not reopened.current.analysis.jobs.results
        finally:
            reopened.close()
