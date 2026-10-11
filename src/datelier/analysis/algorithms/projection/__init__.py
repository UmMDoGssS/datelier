"""Projection methods and their public family type."""

from datelier.analysis.algorithms.projection.gaussian_projection import (
    GaussianProjectionAlgorithm as GaussianProjectionAlgorithm,
)
from datelier.analysis.algorithms.projection.sparse_projection import (
    SparseProjectionAlgorithm as SparseProjectionAlgorithm,
)

ProjectionMethods = GaussianProjectionAlgorithm | SparseProjectionAlgorithm
