"""Type-aware profiles with explicit sampling and separate data-quality counts.

Numeric moments and quantiles use finite values in original units. Non-null and
unique counts exclude nulls but retain NaN/infinity as non-null values. Categorical
counts use a bounded leading cohort, with named missing values and top categories
plus Other. Nested lists profile flattened leaves and separately report container
lengths/shapes; Inspect retains complete object/list values.
"""

from datelier.inspection.profiles.numeric import NumericStatistics as NumericStatistics
from datelier.inspection.profiles.numeric import (
    prepare_numeric_statistics as prepare_numeric_statistics,
)
from datelier.inspection.profiles.prepare import COUNT_ROW_LIMIT as COUNT_ROW_LIMIT
from datelier.inspection.profiles.prepare import (
    MAX_PROFILE_COLUMNS as MAX_PROFILE_COLUMNS,
)
from datelier.inspection.profiles.prepare import ColumnProfile as ColumnProfile
from datelier.inspection.profiles.prepare import Distribution as Distribution
from datelier.inspection.profiles.prepare import ProfileKind as ProfileKind
from datelier.inspection.profiles.prepare import Profiles as Profiles
from datelier.inspection.profiles.prepare import prepare_profiles as prepare_profiles
from datelier.inspection.profiles.prepare import (
    prepare_range_profile as prepare_range_profile,
)
from datelier.inspection.profiles.prepare import profile_kind as profile_kind
from datelier.inspection.profiles.selection import ProfileSelection as ProfileSelection
from datelier.inspection.profiles.tables import ProfileTable as ProfileTable
from datelier.inspection.profiles.tables import (
    prepare_statistics_tables as prepare_statistics_tables,
)
