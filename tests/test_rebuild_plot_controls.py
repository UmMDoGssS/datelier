"""List distribution controls retain leaf semantics and survive session restoration."""

import json
from pathlib import Path

from test_rebuild_comparisons import until

from datelier.application.editor import EditorController
from datelier.application.workspace import capture_session
from datelier.core.column_roles import ColumnRole
from datelier.workspace.sessions.jobs import save_snapshot


def test_list_density_drafts_preserve_source_and_restore_without_explicit_jobs(
    tmp_path: Path,
) -> None:
    source = tmp_path / "lists.jsonl"
    source.write_text(
        "\n".join(
            json.dumps(row)
            for row in (
                {"xs": [1.0, 3.0, None], "label": "a"},
                {"xs": [], "label": "a"},
                {"xs": None, "label": "b"},
                {"xs": [5.0], "label": "b"},
            )
        )
    )
    original = source.read_bytes()
    session = tmp_path / "session.json"
    editor = EditorController()
    try:
        file = editor.current
        file.open(source)
        until(editor, lambda: file.explorer.active is not None)
        file.profiles.choose(("xs",))
        file.profiles.mode = 4
        file.plots.bandwidth, file.plots.seed = 0.25, 71
        until(
            editor,
            lambda: (
                file.explorer.profiles.active is not None
                and file.explorer.profiles.active.comparison is not None
                and file.explorer.profiles.active.comparison.settings.bandwidth == 0.25
            ),
        )
        assert file.profiles.numeric
        assert not next(c for c in file.profiles.choices if c.name == "xs").numeric
        result = file.explorer.profiles.active
        assert result and result.comparison
        assert result.comparison.series[0].count == 3
        assert result.profiles.columns[0].list_statistics
        save_snapshot(session, capture_session(editor), False)
        file.profiles.choose(("label",))
        editor.poll()
        assert not file.profiles.numeric
        assert source.read_bytes() == original
    finally:
        editor.close()
    reopened = EditorController()
    try:
        reopened.open_workspace(session)
        until(
            reopened,
            lambda: (
                not reopened.workspace.busy
                and reopened.current.explorer.profiles.active is not None
            ),
        )
        file = reopened.current
        assert file.profiles.numeric and file.profiles.selected == ("xs",)
        assert file.profiles.mode == 4
        assert file.plots.bandwidth == 0.25 and file.plots.seed == 71
        assert (
            file.inspection
            and file.inspection.dataset.role("xs").role == ColumnRole.LIST_NUMERIC
        )
        assert not file.analysis.jobs.results and not file.text.corpus.busy
        assert source.read_bytes() == original
    finally:
        reopened.close()
