"""Transactional referenced-source import and pipeline replay."""

from dataclasses import dataclass, replace
from pathlib import Path

from datelier.inspection.table import Inspection, prepare_inspection
from datelier.io.importing import load_file
from datelier.io.types import ImportResult
from datelier.pipeline.history import Pipeline
from datelier.pipeline.operations import apply_operation
from datelier.workspace.single.storage import fingerprint, read_workspace
from datelier.workspace.single.types import Workspace


class SourceIssue(ValueError):
    def __init__(
        self, workspace: Workspace, message: str, *, changed: bool = False
    ) -> None:
        self.workspace = workspace
        self.changed = changed
        super().__init__(message)


@dataclass(frozen=True)
class RestoredWorkspace:
    workspace: Workspace
    pipeline: Pipeline
    inspection: Inspection


def restore_workspace(
    path: Path, *, relink: Path | None = None, accept_changed: bool = False
) -> RestoredWorkspace:
    return restore_recipe(
        read_workspace(path), relink=relink, accept_changed=accept_changed
    )


def restore_recipe(
    workspace: Workspace,
    *,
    relink: Path | None = None,
    accept_changed: bool = False,
    imported_override: ImportResult | None = None,
) -> RestoredWorkspace:
    workspace.validate()
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
            changed=True,
        )
    imported = imported_override or load_file(
        source_path, workspace.options, format=workspace.format
    )
    if imported_override is not None and (
        imported.format != workspace.format or imported.options != workspace.options
    ):
        raise ValueError("Prepared source does not match the saved recipe")
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
