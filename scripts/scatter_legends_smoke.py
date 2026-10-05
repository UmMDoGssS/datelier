"""Click native color legends, retain source selection, and render numeric scales."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from imgui_bundle import hello_imgui, imgui, implot, implot3d

from datelier.analysis_types import Algorithm
from datelier.gui import GuiSession, InspectionEvidence, run_gui


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dimensions", type=int, choices=[2, 3], default=2)
    dimensions = parser.parse_args().dimensions
    source = Path("/home/ummdogsss/Downloads/titanic_train.csv")
    before = sha256(source.read_bytes()).hexdigest()
    end2d, end3d = implot.end_plot, implot3d.end_plot
    scale = implot.colormap_scale
    header = imgui.collapsing_header
    labels: tuple[str, ...] = ()
    hidden = False
    legend_pixel = (0.0, 0.0)
    scale_label = ""
    stage, entered, phase = 0, 0, 0
    chosen: frozenset[int] = frozenset()
    observed: dict[str, object] = {}

    def after2d() -> None:
        nonlocal labels, hidden, legend_pixel
        plot = implot.internal.get_current_plot()
        end2d()
        if dimensions != 2:
            return
        group = plot.items
        current = tuple(
            group.get_legend_label(i) for i in range(group.get_legend_count())
        )
        if any(
            "##sex/" in label or "##K-means/" in label or "Missing / nonfinite" in label
            for label in current
        ):
            labels = tuple(label.split("##")[0] for label in current)
            first = group.get_legend_item(0)
            hidden = not first.show
            rect = group.legend.rect_clamped
            legend_pixel = (rect.min.x + 12, rect.min.y + 12)

    def after3d() -> None:
        nonlocal labels, hidden, legend_pixel
        plot = implot3d.internal.get_current_plot()
        end3d()
        if dimensions != 3:
            return
        group = plot.items
        current = tuple(
            group.get_legend_label(i) for i in range(group.get_legend_count())
        )
        labels = tuple(label.split("##")[0] for label in current)
        if current:
            hidden = not group.get_legend_item(0).show
            rect = group.legend.rect_clamped
            legend_pixel = (rect.min.x + 12, rect.min.y + 12)

    def color_scale(
        label: str,
        low: float,
        high: float,
        size: tuple[float, float],
        format: str = "%g",
        flags: int = 0,
        cmap: int | None = None,
    ) -> None:
        nonlocal scale_label
        assert abs(size[1] - imgui.get_item_rect_size().y) < 1
        scale(label, low, high, size, format, flags, cmap)
        scale_label = label

    def no_legacy_header(label: str, flags: int = 0) -> bool:
        assert label != "Color legend"
        return header(label, flags)

    def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
        nonlocal stage, entered, phase, chosen
        active, dashboard = session.loader.active, session.explorer.active
        if active is None or dashboard is None:
            return
        plots, analysis, view = session.plots, session.analysis, session.exploration
        io = imgui.get_io()
        age = evidence.frames - entered
        if stage == 0:
            view.tab = "Relationships"
            plots.choose_chart(f"Scatter {dimensions}D")
            plots.custom_scatter = True
            plots.x_index, plots.y_index, plots.z_index = map(
                plots.numeric.index, ("sibsp", "parch", "fare")
            )
            plots.choose_color("Column")
            plots.color_index = plots.color_columns.index("sex") + 1
            session.explorer.request(active.dataset, plots.settings())
            (
                view.scatter3d_area if dimensions == 3 else view.scatter_area
            ).expanded = True
            stage, entered = 1, evidence.frames
        elif stage == 1 and age > 20 and dashboard.scatters[0].colors is not None:
            assert set(labels) == {"male", "female"}, labels
            points = dashboard.scatters[0]
            assert points.colors is not None
            group = points.colors.series[0]
            chosen = frozenset(int(i) for i in points.row_ids[group.indices])
            session.selection.choose(points.revision, chosen)
            observed["category_legend"] = labels
            stage, entered = 2, evidence.frames
        elif stage in (2, 4):
            if phase == 0 and age > 10:
                io.mouse_pos = imgui.ImVec2(*legend_pixel)
                io.want_set_mouse_pos = True
                phase, entered = 1, evidence.frames
            elif phase == 1 and age > 3:
                io.add_mouse_button_event(0, True)
                phase, entered = 2, evidence.frames
            elif phase == 2 and age > 3:
                io.add_mouse_button_event(0, False)
                phase, entered = 3, evidence.frames
            elif phase == 3 and age > 10:
                assert hidden == (stage == 2), (
                    hidden,
                    stage,
                    legend_pixel,
                    (io.mouse_pos.x, io.mouse_pos.y),
                    labels,
                )
                assert session.selection.row_ids == chosen
                shown = (
                    view.scatter3d.selected_points
                    if dimensions == 3
                    else view.interaction.selected_points
                )
                assert shown == (0 if stage == 2 else len(chosen)), (shown, len(chosen))
                if stage == 2:
                    stage, phase, entered = 4, 0, evidence.frames
                else:
                    observed["native_hide_restore"] = True
                    session.selection.choose(active.dataset.revision, ())
                    plots.choose_color("K-means")
                    analysis.controls.features = ["age", "fare", "sibsp", "parch"]
                    analysis.controls.start(
                        analysis.jobs, active.dataset, Algorithm.KMEANS
                    )
                    stage, entered = 5, evidence.frames
        elif stage == 5 and age > 20:
            if not any(label.startswith("Cluster ") for label in labels):
                return
            assert "Unassigned / excluded" in labels
            assert len([n for n in labels if n.startswith("Cluster ")]) == 3
            observed["kmeans_legend"] = labels
            analysis.source = Algorithm.PCA
            analysis.controls.start(analysis.jobs, active.dataset, Algorithm.PCA)
            stage, entered = 6, evidence.frames
        elif stage == 6 and age > 20:
            points = analysis.plots.active
            if points is None or points.x_name != "PCA 1":
                return
            assert points.colors is not None and points.colors.name == "K-means"
            assert (points.z is not None) == (dimensions == 3)
            assert len([n for n in labels if n.startswith("Cluster ")]) == 3
            observed["reduced_cluster_legend"] = True
            analysis.source = None
            plots.choose_color("Column")
            plots.color_index = plots.color_columns.index("age") + 1
            session.explorer.request(active.dataset, plots.settings())
            stage, entered = 7, evidence.frames
        elif stage == 7 and age > 20:
            if scale_label != "age":
                return
            assert labels == ("Missing / nonfinite",), labels
            assert not analysis.jobs.busy
            observed.update(
                continuous_color_scale=True, missing_legend=True, linked_selection=True
            )
            io.mouse_pos = imgui.ImVec2(2, 2)
            stage, entered = 8, evidence.frames
        elif stage == 8 and age > 10:
            hello_imgui.get_runner_params().app_shall_exit = True

    with (
        patch.object(implot, "end_plot", after2d),
        patch.object(implot3d, "end_plot", after3d),
        patch.object(implot, "colormap_scale", color_scale),
        patch.object(imgui, "collapsing_header", no_legacy_header),
    ):
        evidence = run_gui(source, smoke_frames=2000, on_frame=frame)
    assert stage == 8, (stage, labels)
    assert before == sha256(source.read_bytes()).hexdigest()
    pixels = hello_imgui.final_app_window_screenshot()
    height, width = pixels.shape[:2]
    Path(f"/tmp/datelier-legends-{dimensions}d.ppm").write_bytes(
        f"P6\n{width} {height}\n255\n".encode() + pixels[:, :, :3].tobytes()
    )
    print(
        json.dumps(
            {
                **observed,
                "dimensions": dimensions,
                "frames": evidence.frames,
                "source_preserved": True,
            }
        )
    )


if __name__ == "__main__":
    main()
