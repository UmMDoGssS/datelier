"""Scoped image comparisons with shared physical bins and source-specific outcomes.

Sources explicitly select file fields or confirmed array mappings and independent
record/pixel scopes. Shared bounds make distributions comparable while retaining
units, dtype/channel provenance, source-row links, and missing/corrupt diagnostics.
Restoration retains recipes without scanning collections.
"""

from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSettings as ImageComparisonSettings,
)
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonSource as ImageComparisonSource,
)
from datelier.inspection.images.comparisons.settings import (
    ImageComparisonViewSettings as ImageComparisonViewSettings,
)
