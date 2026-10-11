"""Trusted text recipe records; never selected by file-supplied imports."""

from datelier.inspection.text.comparisons import (
    TextComparisonSettings,
    TextComparisonSource,
    TextComparisonViewSettings,
)
from datelier.inspection.text.display import TextViewport
from datelier.inspection.text.types import (
    TextScope,
    TextSettings,
    TokenizerReference,
    TokenSettings,
    TrainingSettings,
)

RECORDS = (
    TextComparisonSettings,
    TextComparisonSource,
    TextComparisonViewSettings,
    TextViewport,
    TextScope,
    TrainingSettings,
    TextSettings,
    TokenSettings,
    TokenizerReference,
)
