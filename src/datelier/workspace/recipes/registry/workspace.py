"""Trusted workspace recipe records; never selected by file-supplied imports."""

from datelier.workspace.recent import RecentSource
from datelier.workspace.sessions import SessionFile, SessionWorkspace, SourceDraft
from datelier.workspace.single import Workspace, WorkspaceSource, WorkspaceViews

RECORDS = (
    Workspace,
    SessionFile,
    SessionWorkspace,
    SourceDraft,
    RecentSource,
    WorkspaceSource,
    WorkspaceViews,
)
