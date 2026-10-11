"""Public algorithm families and the trusted catalog; estimators load on demand."""

from datelier.analysis.algorithms.base import Algorithm as Algorithm
from datelier.analysis.algorithms.base import ClusteringAlgorithm as ClusteringAlgorithm
from datelier.analysis.algorithms.base import (
    DecompositionAlgorithm as DecompositionAlgorithm,
)
from datelier.analysis.algorithms.registry import ALGORITHMS as ALGORITHMS
from datelier.analysis.algorithms.registry import AlgorithmInstance as AlgorithmInstance
from datelier.analysis.algorithms.registry import is_clustering as is_clustering
