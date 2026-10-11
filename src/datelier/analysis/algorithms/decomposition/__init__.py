"""Decomposition methods and their public family type."""

from datelier.analysis.algorithms.decomposition.factor_analysis import (
    FactorAnalysisAlgorithm as FactorAnalysisAlgorithm,
)
from datelier.analysis.algorithms.decomposition.ica import ICAAlgorithm as ICAAlgorithm
from datelier.analysis.algorithms.decomposition.kernel_pca import (
    KernelPCAAlgorithm as KernelPCAAlgorithm,
)
from datelier.analysis.algorithms.decomposition.nmf import NMFAlgorithm as NMFAlgorithm
from datelier.analysis.algorithms.decomposition.pca import PCAAlgorithm as PCAAlgorithm
from datelier.analysis.algorithms.decomposition.svd import SVDAlgorithm as SVDAlgorithm

DecompositionMethods = (
    SVDAlgorithm
    | ICAAlgorithm
    | FactorAnalysisAlgorithm
    | KernelPCAAlgorithm
    | NMFAlgorithm
    | PCAAlgorithm
)
