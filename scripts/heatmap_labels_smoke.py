"""Live annotated-cell, undefined-value, color-scale and wide-canvas checks."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from unittest.mock import patch

import numpy as np
import polars as pl
from imgui_bundle import hello_imgui, imgui, implot
from numpy.typing import NDArray

from datelier.gui.app import GuiSession, InspectionEvidence, run_gui
from datelier.workspace.preferences import Theme


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--features", type=int, choices=range(2, 17), default=5)
    parser.add_argument("--expanded", action="store_true")
    parser.add_argument("--light", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("/tmp/datelier-heatmap.ppm")
    )
    args = parser.parse_args()
    stage, entered = 0, 0
    cells: NDArray[np.float64] | None = None
    format_seen = ""
    scale = (0.0, 0.0, 0)
    scale_pixel = (0.0, 0.0)
    undefined: set[tuple[float, float]] = set()
    scroll_max = 0.0
    original_heatmap, original_text, original_scale = (
        implot.plot_heatmap,
        implot.plot_text,
        implot.colormap_scale,
    )

    def heatmap(
        label: str,
        values: NDArray[np.float64],
        minimum: float,
        maximum: float,
        label_format: str,
        lo: implot.Point,
        hi: implot.Point,
    ) -> None:
        nonlocal cells, format_seen, scroll_max
        cells, format_seen = values.copy(), label_format
        scroll_max = imgui.get_scroll_max_x()
        original_heatmap(label, values, minimum, maximum, label_format, lo, hi)

    def plot_text(label: str, x: float, y: float) -> None:
        if label == "—":
            undefined.add((x, y))
        original_text(label, x, y)

    def color_scale(
        label: str,
        minimum: float,
        maximum: float,
        size: imgui.ImVec2 | tuple[float, float],
        format: str,
        *,
        cmap: int,
    ) -> None:
        nonlocal scale, scale_pixel
        scale = (minimum, maximum, cmap)
        original_scale(label, minimum, maximum, size, format, cmap=cmap)
        pos = imgui.get_item_rect_min()
        scale_pixel = (pos.x, pos.y)

    with TemporaryDirectory(prefix="datelier-heatmap-") as folder:
        source = args.source or Path(folder) / "data.parquet"
        if args.source is None:
            rows = np.arange(60)
            values = {
                "age": rows,
                "fare": -rows,
                "constant": np.ones(60),
            }
            values.update(
                {f"feature_{i}": np.sin(rows * i) for i in range(3, args.features)}
            )
            pl.DataFrame(values).write_parquet(source)
        before = sha256(source.read_bytes()).hexdigest()

        def frame(session: GuiSession, evidence: InspectionEvidence) -> None:
            nonlocal stage, entered
            active, dashboard = session.loader.active, session.explorer.active
            if active is None or dashboard is None:
                return
            view = session.exploration.relationships
            age = evidence.frames - entered
            assert age < 200, (stage, view.frames)
            if stage == 0:
                names = (
                    ["age", "fare", "pclass", "sibsp", "parch"]
                    if args.source and args.features == 5
                    else list(session.plots.numeric[: args.features])
                )
                assert len(names) == args.features
                session.plots.relationship_features = names
                session.explorer.request(active.dataset, session.plots.settings())
                session.exploration.tab = "Correlations"
                if args.light:
                    session.preferences.apply_theme(Theme.LIGHT)
                stage, entered = 1, evidence.frames
            elif stage == 1 and age > 20:
                data = dashboard.relationships
                assert data is not None and cells is not None
                assert len(data.names) == args.features
                np.testing.assert_allclose(cells, np.nan_to_num(data.values[::-1]))
                assert format_seen == "%.2f"
                assert scale == (-1, 1, implot.Colormap_.rd_bu)
                expected = {
                    (float(j) + 0.5, float(i) + 0.5)
                    for i, j in np.argwhere(~np.isfinite(data.values))
                }
                assert undefined == expected
                assert scale_pixel[0] > 0
                if args.features == 16:
                    assert scroll_max > 0, "wide labels require horizontal space"
                view.area.expanded = args.expanded
                stage, entered = 2, evidence.frames
            elif stage == 2 and age > 20:
                assert view.area.rendered_height >= args.features * 21 + 60
                assert sha256(source.read_bytes()).hexdigest() == before
                imgui.get_io().mouse_pos = imgui.ImVec2(10, 10)
                hello_imgui.get_runner_params().app_shall_exit = True

        with (
            patch.object(implot, "plot_heatmap", side_effect=heatmap),
            patch.object(implot, "plot_text", side_effect=plot_text),
            patch.object(implot, "colormap_scale", side_effect=color_scale),
        ):
            evidence = run_gui(source, smoke_frames=1000, on_frame=frame)
        assert stage == 2
        pixels = cast(NDArray[np.uint8], hello_imgui.final_app_window_screenshot())
        h, w = pixels.shape[:2]
        args.output.write_bytes(
            f"P6\n{w} {h}\n255\n".encode() + pixels[:, :, :3].tobytes()
        )
        report = {
            "frames": evidence.frames,
            "features": args.features,
            "expanded": args.expanded,
            "light_theme": args.light,
            "numeric_cell_format": format_seen,
            "undefined_cells": len(undefined),
            "color_scale": [-1, 1],
            "wide_canvas_scroll_max": scroll_max,
            "source_sha256": before,
        }
        args.output.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
