"""Independent file/view state coordinated by one editor and bounded worker pool.

Each file owns import drafts, history, selections, plots, and modality controllers;
named record views have separate identities and recipes. Switching/reordering
tabs preserves their state. Closing abandons publication and releases owned
caches/jobs without shutting down shared services used by other files.
"""

from datelier.application.sessions.editor import EditorController as EditorController
from datelier.application.sessions.file import FileController as FileController
from datelier.application.sessions.navigation import (
    WorkbenchNavigation as WorkbenchNavigation,
)
