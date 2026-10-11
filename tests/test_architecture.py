"""Keep domain/controller boundaries and source-label identity intact."""

import ast
from pathlib import Path

import pytest

from datelier.gui.components.native import label_text

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "datelier"


def imports(path: Path) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def test_domain_and_controllers_do_not_depend_on_rendering() -> None:
    for subsystem in (
        "application",
        "core",
        "io",
        "pipeline",
        "inspection",
        "analysis",
        "plotting",
        "workspace",
    ):
        for path in (PACKAGE / subsystem).rglob("*.py"):
            assert not any(
                module.startswith(("datelier.gui", "imgui_bundle"))
                for module in imports(path)
            ), path


def test_whole_controllers_are_only_injected_at_gui_composition() -> None:
    composition = {
        "app.py",
        "shell/page.py",
        "shell/assembly.py",
        "shell/inspect_assembly.py",
    }
    root = PACKAGE / "gui"
    for path in root.rglob("*.py"):
        if path.relative_to(root).as_posix() in composition:
            continue
        assert not any(
            module
            in (
                "datelier.application.sessions",
                "datelier.application.sessions.editor",
                "datelier.application.sessions.file",
            )
            for module in imports(path)
        ), path


@pytest.mark.parametrize("value", ["plain", "##", "###name", "a####b", "文本###"])
def test_source_labels_preserve_visible_content_and_cannot_change_widget_ids(
    value: str,
) -> None:
    escaped = label_text(value)
    assert "##" not in escaped
    assert escaped.replace("\u200b", "") == value
