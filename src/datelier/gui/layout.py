"""Default workbench docking topology, independently resettable from recipes."""

from collections.abc import Callable

from imgui_bundle import hello_imgui, imgui

DOCKS = (
    ("MainDockSpace", "ImportSpace", imgui.Dir.left, 0.3),
    ("ImportSpace", "SchemaSpace", imgui.Dir.down, 0.55),
    ("MainDockSpace", "EditSpace", imgui.Dir.right, 0.32),
    ("MainDockSpace", "PlotSpace", imgui.Dir.down, 0.58),
    ("EditSpace", "AnalysisSpace", imgui.Dir.down, 0.65),
)
PANELS = {
    "Explore": "PlotSpace",
    "Open dataset": "ImportSpace",
    "Workspace": "ImportSpace",
    "Table preview": "MainDockSpace",
    "Schema and nulls": "SchemaSpace",
    "Analysis": "AnalysisSpace",
    "Transform and history": "EditSpace",
    "Export table": "EditSpace",
}


def configure_layout(
    params: hello_imgui.RunnerParams, callbacks: dict[str, Callable[[], None]]
) -> None:
    splits = []
    for initial, new, direction, ratio in DOCKS:
        split = hello_imgui.DockingSplit()
        split.initial_dock, split.new_dock = initial, new
        split.direction, split.ratio = direction, ratio
        splits.append(split)
    params.docking_params.docking_splits = splits
    windows = []
    for label, space in PANELS.items():
        window = hello_imgui.DockableWindow()
        window.label, window.dock_space_name = label, space
        window.gui_function = callbacks[label]
        windows.append(window)
    params.docking_params.dockable_windows = windows
