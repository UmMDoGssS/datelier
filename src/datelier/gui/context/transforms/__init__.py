"""Explicit reversible transform forms and contextual history presentation.

Sort/filter/select, casts, missing values, lookup, and derived columns construct
typed operations for background replay. Lookup exposes unmatched-key policy;
derived columns use the constrained expression interface and explicit replacement.
Failed operations preserve active history/table; new edits branch after undo.

The pending Titanic interaction follow-up also calls for direct header sorting,
graphical lookup/missing-value editing, and impact previews. Existing transform
correctness does not establish acceptance of those interaction workflows.
"""

from datelier.gui.context.transforms.base import OperationForm as OperationForm
from datelier.gui.context.transforms.history import HistoryView as HistoryView
from datelier.gui.context.transforms.selection import ColumnsForm as ColumnsForm
from datelier.gui.context.transforms.selection import FilterForm as FilterForm
from datelier.gui.context.transforms.selection import SortForm as SortForm
from datelier.gui.context.transforms.values import CastForm as CastForm
from datelier.gui.context.transforms.values import DerivedForm as DerivedForm
from datelier.gui.context.transforms.values import DropForm as DropForm
from datelier.gui.context.transforms.values import FillForm as FillForm
from datelier.gui.context.transforms.values import LookupForm as LookupForm
from datelier.gui.context.transforms.view import FORMS as FORMS
from datelier.gui.context.transforms.view import TransformSettings as TransformSettings
