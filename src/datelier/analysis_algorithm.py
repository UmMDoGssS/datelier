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

    @property
    def is_clustering(self) -> bool:
        return self in (
            Algorithm.KMEANS,
            Algorithm.DBSCAN,
            Algorithm.HDBSCAN,
            Algorithm.OPTICS,
            Algorithm.MINIBATCH_KMEANS,
            Algorithm.GAUSSIAN_MIXTURE,
            Algorithm.BAYESIAN_MIXTURE,
            Algorithm.AGGLOMERATIVE,
            Algorithm.BIRCH,
            Algorithm.MEAN_SHIFT,
            Algorithm.SPECTRAL_CLUSTERING,
            Algorithm.AFFINITY_PROPAGATION,
        )
