"""Trusted text recipe records; never selected by file-supplied imports."""

from datelier.inspection.text.comparisons.settings import (
    TextComparisonSettings,
    TextComparisonSource,
    TextComparisonViewSettings,
)
from datelier.inspection.text.types import (
    TextScope,
    TextSettings,
    TokenizerReference,
    TokenSettings,
    TrainingSettings,
)
from datelier.inspection.text.viewport import TextViewport

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
