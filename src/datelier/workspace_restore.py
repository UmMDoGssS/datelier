"""Transactional referenced-source import and pipeline replay."""

from dataclasses import dataclass, replace
from pathlib import Path

from datelier.importing import load_file
from datelier.inspection import Inspection, prepare_inspection
from datelier.operations import apply_operation
from datelier.pipeline import Pipeline
from datelier.workspace_types import Workspace
from datelier.workspaces import fingerprint, read_workspace


class SourceIssue(ValueError):
    def __init__(self, workspace: Workspace, message: str) -> None:
        self.workspace = workspace
        super().__init__(message)


@dataclass(frozen=True)
class RestoredWorkspace:
    workspace: Workspace
    pipeline: Pipeline
    inspection: Inspection


def restore_workspace(
    path: Path, *, relink: Path | None = None, accept_changed: bool = False
) -> RestoredWorkspace:
    workspace = read_workspace(path)
    source_path = relink if relink is not None else Path(workspace.source.path)
    try:
        checked = fingerprint(source_path)
    except OSError as error:
        raise SourceIssue(
            workspace,
            f"Source is missing or unreadable: {source_path}. Relink its source.",
        ) from error
    if checked.sha256 != workspace.source.sha256 and not accept_changed:
        raise SourceIssue(
            workspace,
            "Source content changed. Choose the original file or explicitly "
            "accept the current source and replay its recipes.",
        )
    imported = load_file(source_path, workspace.options, format=workspace.format)
    after = fingerprint(source_path)
    reference = imported.dataset.source
    if checked != after or (reference.size_bytes, reference.modified_ns) != (
        checked.size_bytes,
        checked.modified_ns,
    ):
        raise ValueError("Source changed while restoring; retry")
    workspace = replace(workspace, source=checked)
    source = imported.dataset
    current, result = source, source
    # Validate redo recipes too, retaining only the chosen cursor's active table.
    for index, operation in enumerate(workspace.history, 1):
        result = apply_operation(result, operation)
        if index == workspace.cursor:
            current = result
    pipeline = Pipeline(source, current, workspace.history, workspace.cursor)
    inspection = prepare_inspection(replace(imported, dataset=current))
    return RestoredWorkspace(workspace, pipeline, inspection)
