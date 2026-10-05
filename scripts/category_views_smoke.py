"""Reopen migrated category views and new violin settings in the native GUI."""

import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from imgui_bundle import hello_imgui

from datelier.category_charts import CategoryRepresentation as Mode
from datelier.category_charts import CategorySettings
from datelier.distributions import DistributionSettings
from datelier.exploration import PlotSettings
from datelier.gui import GuiSession, InspectionEvidence, run_gui
from datelier.importing import load_file
from datelier.workspace_types import Workspace, WorkspaceViews
from datelier.workspaces import reference_source, save_workspace


def check_view(session: GuiSession, mode: Mode, evidence: InspectionEvidence) -> bool:
    dashboard = session.explorer.active
    if dashboard is None or evidence.frames < 30:
        return False
    view = session.exploration
    assert not session.analysis.jobs.busy and not session.analysis.jobs.results
    if mode == Mode.COUNTS:
        group = session.explorer.profiles.active
        if group is None:
            return False
        assert view.active_tab == "Profiles"
        assert view.profile.selection.columns == ("sex",)
        assert view.profile.area.height == 310
        assert dashboard.category_chart is None
        assert len(group.profiles.columns) == 1
        profile = group.profiles.columns[0]
        assert profile.name == "sex"
        assert sum(profile.distribution.counts) == 850
        assert set(profile.distribution.labels) == {"male", "female"}
    else:
        chart = dashboard.category_chart
        assert chart is not None
        expected = Mode.BOX if mode == Mode.MEAN else mode
        assert view.active_tab == "Relationships"
        assert view.categories.area.height == 310
        assert session.plots.relationship_chart == expected.value
        assert chart.settings.representation == expected
        assert chart.settings.category == "sex" and chart.settings.value == "age"
        assert chart.labels == ("male", "female") and chart.counts.sum() == 676
        assert chart.settings.bandwidth == 0.75 and chart.settings.seed == 17
    return True


def main() -> None:
    source = Path("/home/ummdogsss/Downloads/titanic_train.csv")
    before = sha256(source.read_bytes()).hexdigest()
    imported = load_file(source)
    outcomes: dict[str, object] = {}
    with TemporaryDirectory(prefix="datelier-category-views-") as folder:
        root = Path(folder)
        for mode in (Mode.COUNTS, Mode.MEAN, Mode.VIOLIN):
            category = CategorySettings(
                "sex",
                mode,
                value=None if mode == Mode.COUNTS else "age",
                bandwidth=0.75,
                seed=17,
            )
            initial = root / f"initial-{mode.name}.datelier"
            saved = root / f"saved-{mode.name}.datelier"
            save_workspace(
                initial,
                Workspace(
                    reference_source(imported.dataset.source),
                    imported.format,
                    imported.options,
                    plots=PlotSettings(
                        comparison=DistributionSettings(bandwidth=0.75, seed=17),
                        category_chart=category,
                    ),
                    views=WorkspaceViews(
                        tab="Relationships",
                        profile_selection=("age",),
                        profile_mode=4,
                        category_height=310,
                    ),
                ),
            )
            stage = 0

            def first(
                session: GuiSession,
                evidence: InspectionEvidence,
                restored_mode: Mode = mode,
                save_path: Path = saved,
            ) -> None:
                nonlocal stage
                if stage == 0 and check_view(session, restored_mode, evidence):
                    session.workspace.path = str(save_path)
                    session.workspace.save(session)
                    stage = 1
                elif stage == 1 and not session.workspace.jobs.busy:
                    assert session.workspace.jobs.saved is not None, (
                        session.workspace.jobs.message
                    )
                    stage = 2
                    hello_imgui.get_runner_params().app_shall_exit = True

            run_gui(initial_workspace=initial, smoke_frames=1200, on_frame=first)
            assert stage == 2
            pixels = hello_imgui.final_app_window_screenshot()
            height, width = pixels.shape[:2]
            Path(f"/tmp/datelier-category-{mode.name.lower()}.ppm").write_bytes(
                f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
            )
            reopened = False

            def second(
                session: GuiSession,
                evidence: InspectionEvidence,
                restored_mode: Mode = mode,
            ) -> None:
                nonlocal reopened
                if check_view(session, restored_mode, evidence):
                    reopened = True
                    hello_imgui.get_runner_params().app_shall_exit = True

            run_gui(initial_workspace=saved, smoke_frames=1200, on_frame=second)
            assert reopened
            outcomes[mode.value] = {"saved_and_reopened": True, "height": 310}
    assert before == sha256(source.read_bytes()).hexdigest()
    print(json.dumps({**outcomes, "implicit_ml_runs": 0, "source_preserved": True}))


if __name__ == "__main__":
    main()
