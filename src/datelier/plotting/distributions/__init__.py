"""Numeric overlays and category distributions prepared outside GUI callbacks.

Histograms share bins and optionally use density/z-scores; statistics retain
original units. KDE uses Gaussian kernels with Scott bandwidth and a multiplier.
KDE/ECDF/violin use seeded source-ID samples; box quartiles/Tukey whiskers are
exact over retained finite values, with bounded sampled displayed outliers.
Category distributions retain named missing groups and top categories plus Other.
"""

from datelier.plotting.distributions.categories import (
    prepare_category_distributions as prepare_category_distributions,
)
from datelier.plotting.distributions.numeric import Comparison as Comparison
from datelier.plotting.distributions.numeric import (
    DistributionSettings as DistributionSettings,
)
from datelier.plotting.distributions.numeric import (
    NumericDistribution as NumericDistribution,
)
from datelier.plotting.distributions.numeric import (
    prepare_comparison as prepare_comparison,
)
from datelier.plotting.distributions.numeric import (
    prepare_series_comparison as prepare_series_comparison,
)
