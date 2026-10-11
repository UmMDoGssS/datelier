"""Legacy projection names are aliases to executable methods."""

from datelier.analysis.algorithms.projection import (
    GaussianProjectionAlgorithm as GaussianProjectionParameters,
)
from datelier.analysis.algorithms.projection import (
    SparseProjectionAlgorithm as SparseProjectionParameters,
)

ProjectionParameters = GaussianProjectionParameters | SparseProjectionParameters
