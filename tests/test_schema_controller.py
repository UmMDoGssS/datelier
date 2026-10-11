"""Prepared schema commands preserve revision, type and edit boundaries."""

from pathlib import Path

from datelier.application.tabular import SchemaController
from datelier.core import ColumnRole
from datelier.inspection.table import prepare_inspection
from datelier.io.importing import load_file
from datelier.pipeline import Pipeline, SetColumnRole


def test_prepared_schema_reuse_and_reversible_role_command(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("id,label,value\n1,a,4\n2,b,5\n3,a,\n")
    inspection = prepare_inspection(load_file(path))
    requests: list[SetColumnRole] = []
    controller = SchemaController(requests.append)
    controller.refresh(inspection, busy=False)
    snapshot = controller.snapshot
    assert snapshot is not None
    assert snapshot.rows == 3
    assert snapshot.columns[2].role.nonnull == 2
    assert snapshot.columns[0].role.role == ColumnRole.IDENTIFIER
    controller.refresh(inspection, busy=True)
    assert controller.snapshot is snapshot
    controller.set_role(snapshot.revision, "id", ColumnRole.NUMERIC)
    assert not requests and controller.error
    controller.refresh(inspection, busy=False)
    controller.set_role(snapshot.revision, "id", ColumnRole.NUMERIC)
    assert requests == [SetColumnRole("id", ColumnRole.NUMERIC)]
    assert controller.busy and not controller.error
    pipeline = Pipeline.start(inspection.dataset).apply(requests[0])
    assert pipeline.current.role("id").role == ColumnRole.NUMERIC
    assert pipeline.current.table.equals(inspection.dataset.table)
    assert pipeline.current.row_ids.equals(inspection.dataset.row_ids)
    assert pipeline.undo().current.role("id").role == ColumnRole.IDENTIFIER


def test_stale_unavailable_and_failed_commands_do_not_publish(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("label,value\na,4\nb,5\n")
    inspection = prepare_inspection(load_file(path))
    requests: list[SetColumnRole] = []
    controller = SchemaController(requests.append)
    controller.refresh(inspection, busy=False)
    controller.set_role(inspection.dataset.revision, "label", ColumnRole.NUMERIC)
    controller.set_role(inspection.dataset.revision, "missing", None)
    assert not requests
    replacement = prepare_inspection(load_file(path))
    controller.refresh(replacement, busy=False)
    controller.set_role(inspection.dataset.revision, "value", ColumnRole.CATEGORY)
    assert not requests and "changed" in controller.error
    controller.refresh(None, busy=False)
    assert controller.snapshot is None
    controller.set_role(replacement.dataset.revision, "value", None)
    assert not requests

    def fail(operation: SetColumnRole) -> None:
        raise ValueError("Editor closed")

    failed = SchemaController(fail)
    failed.refresh(replacement, busy=False)
    failed.set_role(replacement.dataset.revision, "value", ColumnRole.CATEGORY)
    assert failed.error == "Editor closed" and not failed.busy
