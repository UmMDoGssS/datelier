"""Exact corpus statistics with bounded chart buffers and complete raw tables.

Profiles retain document/token totals, original and normalized lengths, quantiles,
vocabulary/hapax ratios, entropy in bits, token/document frequencies, and record
outcomes. Empty, null, failed, and tokenless records remain distinguishable.
List[Text] inputs stream leaves with their source row and nested element path.
"""

from datelier.inspection.text.profiles.statistics import (
    LengthStatistics as LengthStatistics,
)
from datelier.inspection.text.profiles.statistics import TextProfile as TextProfile
from datelier.inspection.text.profiles.statistics import (
    calculate_profile as calculate_profile,
)
from datelier.inspection.text.profiles.statistics import (
    length_histogram as length_histogram,
)
from datelier.inspection.text.profiles.statistics import (
    summarize_lengths as summarize_lengths,
)
