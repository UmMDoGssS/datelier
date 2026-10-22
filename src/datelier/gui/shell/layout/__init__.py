"""Adaptive docking, menus, file tabs, and panel visibility.

Default layouts adapt to window size; custom docking and splitters persist.
View-menu actions restore every closable panel. Reset layout changes presentation
only. Layout migrations reset obsolete native state while retaining data recipes,
theme, plot settings, and selections.
"""

from datelier.gui.shell.layout.docking import DockHost as DockHost
from datelier.gui.shell.layout.docking import DockPanel as DockPanel
from datelier.gui.shell.layout.menu import Menu as Menu
from datelier.gui.shell.layout.menu import MenuAction as MenuAction
from datelier.gui.shell.layout.menu import MenuBar as MenuBar
from datelier.gui.shell.layout.menu import RecentMenu as RecentMenu
from datelier.gui.shell.layout.navigation import CanvasTabs as CanvasTabs
from datelier.gui.shell.layout.navigation import FileTab as FileTab
from datelier.gui.shell.layout.navigation import FileTabs as FileTabs
from datelier.gui.shell.layout.navigation import NamedTab as NamedTab
from datelier.gui.shell.layout.navigation import native_order as native_order
