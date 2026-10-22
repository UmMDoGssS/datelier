"""Source-bound numeric/categorical column comparisons with shared plot domains.

Mappings explicitly name each file, record view, and column. Numeric series share
histogram bins and exclude/report null/nonfinite values; categories share pooled
top values and Other. Density gives numeric series unit area; proportions divide
category counts by that source's row count. Bin selection validates the source
revision and returns bounded row IDs plus the full match count.
"""

from datelier.inspection.comparisons.types import ComparisonInput as ComparisonInput
from datelier.inspection.comparisons.types import (
    ComparisonSelection as ComparisonSelection,
)
from datelier.inspection.comparisons.types import Origin as Origin
from datelier.inspection.comparisons.types import (
    PreparedComparison as PreparedComparison,
)
from datelier.inspection.comparisons.types import SeriesSummary as SeriesSummary
