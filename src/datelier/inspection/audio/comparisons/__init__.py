"""Explicit header or exact-signal comparisons across file fields/array mappings.

Each source has its own range, scope, rate, and thresholds. Distributions share
bins; amplitude curves separate compatible units, dtypes, and channels. Record
outcomes and selection links retain file/view identity. Saved recipes restore
without scanning signals or starting sound.
"""

from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSettings as AudioComparisonSettings,
)
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonSource as AudioComparisonSource,
)
from datelier.inspection.audio.comparisons.settings import (
    AudioComparisonViewSettings as AudioComparisonViewSettings,
)
