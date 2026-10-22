"""Structured-tree browsing, exact numeric slices, and confirmed record mappings.

Controllers turn prepared metadata into node/member choices and explicit worker
requests. Each named view has its own transformation/selection state; supporting
fields use aligned original record indices. Restored mapped arrays remain
metadata-only until explicit scalar-record preparation, while automatic aligned
NPZ tables reopen their scalar columns in workers.
"""

from datelier.application.sources.numeric import (
    NumericSourceController as NumericSourceController,
)
from datelier.application.sources.objects import ObjectController as ObjectController
from datelier.application.sources.records import (
    ArrayRecordController as ArrayRecordController,
)
