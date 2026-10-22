"""Explicit cross-file text comparisons using one shared tokenizer configuration.

Each mapped source keeps its own encoding, interpretation, and corpus scope.
Length plots share bins; exact token/document frequencies share a vocabulary
order. Proportions use decoded documents for lengths/document frequency and
counted tokens for token frequency. Saved recipes never trigger corpus work.
"""

from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings as TextComparisonSettings,
)
from datelier.inspection.text.comparisons.settings import (
    TextComparisonSource as TextComparisonSource,
)
from datelier.inspection.text.comparisons.settings import (
    TextComparisonViewSettings as TextComparisonViewSettings,
)
