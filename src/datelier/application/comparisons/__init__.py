"""Editor-owned column, text, image, and audio comparison controllers.

A shared source catalog identifies available file/views. Each family retains
explicit mappings, drafts, settings, and scoped selection commands. Refresh
prunes closed sources and rejects results from changed revisions; navigation
activates the mapped source rather than matching row numbers across files.
Media/text preparation is explicit and saved recipes restore idle.
"""

from datelier.application.comparisons.base import (
    ComparisonController as ComparisonController,
)
from datelier.application.comparisons.base import ComparisonEntry as ComparisonEntry
from datelier.application.comparisons.base import ComparisonFamily as ComparisonFamily
from datelier.application.comparisons.hub import ComparisonHub as ComparisonHub
