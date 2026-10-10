"""Default workbench docking topology, independently resettable from recipes."""

from collections.abc import Callable

from imgui_bundle import hello_imgui, imgui

DOCKS = (
    ("MainDockSpace", "SourceSpace", imgui.Dir.left, 0.172),
    ("MainDockSpace", "ContextSpace", imgui.Dir.right, 0.265),
    ("MainDockSpace", "TableSpace", imgui.Dir.down, 0.32),
)
PANELS = {
    "Source browser": "SourceSpace",
    "Explore": "MainDockSpace",
    "Context": "ContextSpace",
    "Table preview": "TableSpace",
}


def configure_layout(
    params: hello_imgui.RunnerParams,
    callbacks: dict[str, Callable[[], None]],
    *,
    compact: bool = False,
) -> None:
    splits = []
    for initial, new, direction, ratio in DOCKS:
        if compact and new == "ContextSpace":
            continue
        if compact and new == "SourceSpace":
            ratio = 0.215
        split = hello_imgui.DockingSplit()
        split.initial_dock, split.new_dock = initial, new
        split.direction, split.ratio = direction, ratio
        splits.append(split)
    params.docking_params.docking_splits = splits
    windows = []
    for label, space in PANELS.items():
        window = hello_imgui.DockableWindow()
        window.label, window.dock_space_name = (
            label,
            ("MainDockSpace" if compact and label == "Context" else space),
        )
        if compact and label == "Context":
            window.is_visible = False
        window.gui_function = callbacks[label]
        windows.append(window)
    params.docking_params.dockable_windows = windows
