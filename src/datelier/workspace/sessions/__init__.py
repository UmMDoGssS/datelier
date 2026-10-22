"""Whole-editor workspace contracts, storage, migration, and source recovery.

Session v3/layout v2 retain per-file and named-view recipes plus bounded row
selections. Legacy single-source workspaces become one-tab sessions; obsolete
layout state resets with a notice while recipes survive. Source paths are saved
relative to the workspace. Invalid topology/recipes fail before installation;
individual import failures become recoverable tabs.
"""

from datelier.workspace.sessions.types import SessionFile as SessionFile
from datelier.workspace.sessions.types import SessionWorkspace as SessionWorkspace
from datelier.workspace.sessions.types import SourceDraft as SourceDraft
