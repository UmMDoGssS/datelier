"""Available methods and their output family."""

from enum import StrEnum


class Algorithm(StrEnum):
    PCA = "PCA"
    TSNE = "t-SNE"
    UMAP = "UMAP"
    KMEANS = "K-means"
    DBSCAN = "DBSCAN"
    HDBSCAN = "HDBSCAN"
    OPTICS = "OPTICS"
    MINIBATCH_KMEANS = "Mini-batch K-means"
    GAUSSIAN_MIXTURE = "Gaussian mixture"
    BAYESIAN_MIXTURE = "Bayesian Gaussian mixture"
    AGGLOMERATIVE = "Agglomerative"
    BIRCH = "Birch"
    MEAN_SHIFT = "Mean shift"
    SPECTRAL_CLUSTERING = "Spectral clustering"
    AFFINITY_PROPAGATION = "Affinity propagation"
    SVD = "Truncated SVD"
    ICA = "FastICA"
    FACTOR_ANALYSIS = "Factor analysis"
    KERNEL_PCA = "Kernel PCA"
    NMF = "NMF"
    GAUSSIAN_PROJECTION = "Gaussian random projection"
    SPARSE_PROJECTION = "Sparse random projection"
    ISOMAP = "Isomap"
    MDS = "MDS"
    SPECTRAL_EMBEDDING = "Spectral embedding"
    LLE = "Locally linear embedding"

    @property
    def is_clustering(self) -> bool:
        from datelier.analysis.algorithms import is_clustering

        return is_clustering(self)
