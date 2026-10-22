"""Shared gallery/detail record preparation for tables and direct media sources.

Scopes select current rows, ranges, linked selections, or seeded source-ID samples.
Primary fields drive specialized previews; supporting fields retain full typed
values, including nested containers. Sorting changes display positions without
changing record identity. Cache and page limits do not truncate source values.
"""

from datelier.inspection.records.types import InspectSettings as InspectSettings
from datelier.inspection.records.types import RecordCard as RecordCard
from datelier.inspection.records.types import RecordField as RecordField
from datelier.inspection.records.types import RecordMode as RecordMode
from datelier.inspection.records.types import RecordPage as RecordPage
from datelier.inspection.records.types import RecordSet as RecordSet
