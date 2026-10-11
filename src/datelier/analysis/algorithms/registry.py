"""Explicit trusted algorithm catalog; importing it never loads estimators."""

from typing import TYPE_CHECKING

from datelier.analysis.algorithm import Algorithm as AlgorithmId
from datelier.analysis.algorithms.affinity_propagation import (
    AffinityPropagationAlgorithm,
)
from datelier.analysis.algorithms.agglomerative import AgglomerativeAlgorithm
from datelier.analysis.algorithms.base import ClusteringAlgorithm
from datelier.analysis.algorithms.bayesian_mixture import BayesianMixtureAlgorithm
from datelier.analysis.algorithms.birch import BirchAlgorithm
from datelier.analysis.algorithms.dbscan import DBSCANAlgorithm
from datelier.analysis.algorithms.factor_analysis import FactorAnalysisAlgorithm
from datelier.analysis.algorithms.gaussian_mixture import GaussianMixtureAlgorithm
from datelier.analysis.algorithms.gaussian_projection import GaussianProjectionAlgorithm
from datelier.analysis.algorithms.hdbscan import HDBSCANAlgorithm
from datelier.analysis.algorithms.ica import ICAAlgorithm
from datelier.analysis.algorithms.isomap import IsomapAlgorithm
from datelier.analysis.algorithms.kernel_pca import KernelPCAAlgorithm
from datelier.analysis.algorithms.kmeans import KMeansAlgorithm
from datelier.analysis.algorithms.lle import LLEAlgorithm
from datelier.analysis.algorithms.mds import MDSAlgorithm
from datelier.analysis.algorithms.mean_shift import MeanShiftAlgorithm
from datelier.analysis.algorithms.mini_batch import MiniBatchAlgorithm
from datelier.analysis.algorithms.nmf import NMFAlgorithm
from datelier.analysis.algorithms.optics import OPTICSAlgorithm
from datelier.analysis.algorithms.pca import PCAAlgorithm
from datelier.analysis.algorithms.sparse_projection import SparseProjectionAlgorithm
from datelier.analysis.algorithms.spectral_clustering import SpectralClusteringAlgorithm
from datelier.analysis.algorithms.spectral_embedding import SpectralEmbeddingAlgorithm
from datelier.analysis.algorithms.svd import SVDAlgorithm
from datelier.analysis.algorithms.tsne import TSNEAlgorithm
from datelier.analysis.algorithms.umap import UMAPAlgorithm

if TYPE_CHECKING:
    from datelier.analysis.types import Parameters

ALGORITHMS: dict[AlgorithmId, type[Parameters]] = {
    builder.algorithm: builder
    for builder in (
        KMeansAlgorithm,
        DBSCANAlgorithm,
        HDBSCANAlgorithm,
        OPTICSAlgorithm,
        MiniBatchAlgorithm,
        GaussianMixtureAlgorithm,
        BayesianMixtureAlgorithm,
        AgglomerativeAlgorithm,
        BirchAlgorithm,
        MeanShiftAlgorithm,
        SpectralClusteringAlgorithm,
        AffinityPropagationAlgorithm,
        SVDAlgorithm,
        ICAAlgorithm,
        FactorAnalysisAlgorithm,
        KernelPCAAlgorithm,
        NMFAlgorithm,
        GaussianProjectionAlgorithm,
        SparseProjectionAlgorithm,
        IsomapAlgorithm,
        MDSAlgorithm,
        SpectralEmbeddingAlgorithm,
        LLEAlgorithm,
        PCAAlgorithm,
        TSNEAlgorithm,
        UMAPAlgorithm,
    )
}


def is_clustering(identifier: AlgorithmId) -> bool:
    return issubclass(ALGORITHMS[identifier], ClusteringAlgorithm)
