"""Clustering methods and their public family type."""

from datelier.analysis.algorithms.clustering.affinity_propagation import (
    AffinityPropagationAlgorithm as AffinityPropagationAlgorithm,
)
from datelier.analysis.algorithms.clustering.agglomerative import (
    AgglomerativeAlgorithm as AgglomerativeAlgorithm,
)
from datelier.analysis.algorithms.clustering.bayesian_mixture import (
    BayesianMixtureAlgorithm as BayesianMixtureAlgorithm,
)
from datelier.analysis.algorithms.clustering.birch import (
    BirchAlgorithm as BirchAlgorithm,
)
from datelier.analysis.algorithms.clustering.dbscan import (
    DBSCANAlgorithm as DBSCANAlgorithm,
)
from datelier.analysis.algorithms.clustering.gaussian_mixture import (
    GaussianMixtureAlgorithm as GaussianMixtureAlgorithm,
)
from datelier.analysis.algorithms.clustering.hdbscan import (
    HDBSCANAlgorithm as HDBSCANAlgorithm,
)
from datelier.analysis.algorithms.clustering.kmeans import (
    KMeansAlgorithm as KMeansAlgorithm,
)
from datelier.analysis.algorithms.clustering.mean_shift import (
    MeanShiftAlgorithm as MeanShiftAlgorithm,
)
from datelier.analysis.algorithms.clustering.mini_batch import (
    MiniBatchAlgorithm as MiniBatchAlgorithm,
)
from datelier.analysis.algorithms.clustering.optics import (
    OPTICSAlgorithm as OPTICSAlgorithm,
)
from datelier.analysis.algorithms.clustering.spectral_clustering import (
    SpectralClusteringAlgorithm as SpectralClusteringAlgorithm,
)

ClusteringMethods = (
    KMeansAlgorithm
    | DBSCANAlgorithm
    | HDBSCANAlgorithm
    | OPTICSAlgorithm
    | MiniBatchAlgorithm
    | GaussianMixtureAlgorithm
    | BayesianMixtureAlgorithm
    | AgglomerativeAlgorithm
    | BirchAlgorithm
    | MeanShiftAlgorithm
    | SpectralClusteringAlgorithm
    | AffinityPropagationAlgorithm
)
