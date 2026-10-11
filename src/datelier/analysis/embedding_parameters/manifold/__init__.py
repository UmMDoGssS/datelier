"""Legacy manifold names are aliases to executable methods."""

from datelier.analysis.algorithms.manifold import (
    IsomapAlgorithm as IsomapParameters,
)
from datelier.analysis.algorithms.manifold import (
    LLEAlgorithm as LLEParameters,
)
from datelier.analysis.algorithms.manifold import (
    MDSAlgorithm as MDSParameters,
)
from datelier.analysis.algorithms.manifold import (
    SpectralEmbeddingAlgorithm as SpectralEmbeddingParameters,
)

ManifoldParameters = (
    IsomapParameters | MDSParameters | SpectralEmbeddingParameters | LLEParameters
)
