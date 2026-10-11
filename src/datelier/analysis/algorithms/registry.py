"""Explicit trusted algorithm catalog; importing it never loads estimators."""

from typing import cast, get_args

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.base import ClusteringAlgorithm
from datelier.analysis.algorithms.clustering import ClusteringMethods
from datelier.analysis.algorithms.decomposition import DecompositionMethods
from datelier.analysis.algorithms.manifold import ManifoldMethods
from datelier.analysis.algorithms.projection import ProjectionMethods

AlgorithmInstance = (
    ClusteringMethods | DecompositionMethods | ProjectionMethods | ManifoldMethods
)
# Family unions contain trusted local classes, never recipe contents.
_ALGORITHM_TYPES = cast(
    tuple[type[AlgorithmInstance], ...], get_args(AlgorithmInstance)
)
ALGORITHMS: dict[AlgorithmId, type[AlgorithmInstance]] = {
    method.algorithm: method for method in _ALGORITHM_TYPES
}


def is_clustering(identifier: AlgorithmId) -> bool:
    return issubclass(ALGORITHMS[identifier], ClusteringAlgorithm)
