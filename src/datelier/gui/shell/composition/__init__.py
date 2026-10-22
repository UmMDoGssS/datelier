"""Explicit editor/file/Inspect wiring and ownership of native component lifetimes.

This boundary may consume whole controllers to inject feature-specific prepared
state and commands into children. Specialized routes share selectors, viewports,
and media primitives. Close native owners before renderer shutdown; SharedView
mounts content without transferring its lifetime to a temporary container.
"""

from datelier.gui.shell.composition.files import FileComponents as FileComponents
from datelier.gui.shell.composition.files import assemble_file as assemble_file
from datelier.gui.shell.composition.inspect import (
    InspectComponents as InspectComponents,
)
from datelier.gui.shell.composition.inspect import assemble_inspect as assemble_inspect
from datelier.gui.shell.composition.page import WorkbenchPage as WorkbenchPage
