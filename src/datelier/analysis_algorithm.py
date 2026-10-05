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

    @property
    def is_clustering(self) -> bool:
        return self in (
            Algorithm.KMEANS,
            Algorithm.DBSCAN,
            Algorithm.HDBSCAN,
            Algorithm.OPTICS,
        )
