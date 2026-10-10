"""Targets cannot cross file, record-view, revision or frame boundaries."""

from uuid import uuid4

from datelier.core.dataset import DatasetRevision
from datelier.gui.components.base import FrameContext
from datelier.gui.components.probe import GuiProbe, ViewScope


def test_probe_namespaces_and_frame_retention() -> None:
    revision = DatasetRevision(uuid4())
    scopes = (
        ViewScope("first", "records", revision),
        ViewScope("second", "records", revision),
        ViewScope("first", "other", revision),
        ViewScope("first", "records", DatasetRevision(revision.dataset_id)),
    )
    probe = GuiProbe()
    for index, scope in enumerate(scopes):
        FrameContext(scope, probe).child("schema").child("roles").record(
            "id", (float(index), 10)
        )
    for index, scope in enumerate(scopes):
        assert probe.point(scope, "schema", "roles", "id") == (float(index), 10)
    assert probe.point(scopes[0], "unknown") is None
    probe.begin_frame()
    assert not probe.targets
