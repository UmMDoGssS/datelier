"""Manifold methods and their public family type."""

from datelier.analysis.algorithms.manifold.isomap import (
    IsomapAlgorithm as IsomapAlgorithm,
)
from datelier.analysis.algorithms.manifold.lle import LLEAlgorithm as LLEAlgorithm
from datelier.analysis.algorithms.manifold.mds import MDSAlgorithm as MDSAlgorithm
from datelier.analysis.algorithms.manifold.spectral_embedding import (
    SpectralEmbeddingAlgorithm as SpectralEmbeddingAlgorithm,
)
from datelier.analysis.algorithms.manifold.tsne import TSNEAlgorithm as TSNEAlgorithm
from datelier.analysis.algorithms.manifold.umap import UMAPAlgorithm as UMAPAlgorithm

ManifoldMethods = (
    IsomapAlgorithm
    | MDSAlgorithm
    | SpectralEmbeddingAlgorithm
    | LLEAlgorithm
    | TSNEAlgorithm
    | UMAPAlgorithm
)
