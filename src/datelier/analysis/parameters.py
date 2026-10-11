"""Compatibility exports; parameter definitions live with concrete algorithms."""

from datelier.analysis.algorithm import Algorithm
from datelier.analysis.algorithms.affinity_propagation import (
    AffinityPropagationParameters as AffinityPropagationParameters,
)
from datelier.analysis.algorithms.agglomerative import (
    AgglomerativeParameters as AgglomerativeParameters,
)
from datelier.analysis.algorithms.bayesian_mixture import (
    BayesianMixtureParameters as BayesianMixtureParameters,
)
from datelier.analysis.algorithms.birch import BirchParameters as BirchParameters
from datelier.analysis.algorithms.dbscan import DBSCANParameters as DBSCANParameters
from datelier.analysis.algorithms.factor_analysis import (
    FactorAnalysisParameters as FactorAnalysisParameters,
)
from datelier.analysis.algorithms.gaussian_mixture import (
    GaussianMixtureParameters as GaussianMixtureParameters,
)
from datelier.analysis.algorithms.gaussian_projection import (
    GaussianProjectionParameters as GaussianProjectionParameters,
)
from datelier.analysis.algorithms.hdbscan import HDBSCANParameters as HDBSCANParameters
from datelier.analysis.algorithms.ica import ICAParameters as ICAParameters
from datelier.analysis.algorithms.isomap import IsomapParameters as IsomapParameters
from datelier.analysis.algorithms.kernel_pca import (
    KernelPCAParameters as KernelPCAParameters,
)
from datelier.analysis.algorithms.lle import LLEParameters as LLEParameters
from datelier.analysis.algorithms.mds import MDSParameters as MDSParameters
from datelier.analysis.algorithms.mean_shift import (
    MeanShiftParameters as MeanShiftParameters,
)
from datelier.analysis.algorithms.mini_batch import (
    MiniBatchParameters as MiniBatchParameters,
)
from datelier.analysis.algorithms.nmf import NMFParameters as NMFParameters
from datelier.analysis.algorithms.optics import OPTICSParameters as OPTICSParameters
from datelier.analysis.algorithms.registry import ALGORITHMS
from datelier.analysis.algorithms.sparse_projection import (
    SparseProjectionParameters as SparseProjectionParameters,
)
from datelier.analysis.algorithms.spectral_clustering import (
    SpectralClusteringParameters as SpectralClusteringParameters,
)
from datelier.analysis.algorithms.spectral_embedding import (
    SpectralEmbeddingParameters as SpectralEmbeddingParameters,
)
from datelier.analysis.algorithms.svd import SVDParameters as SVDParameters
from datelier.analysis.schema import validate_parameters as validate_parameters

ExtraParameters = (
    DBSCANParameters
    | HDBSCANParameters
    | OPTICSParameters
    | MiniBatchParameters
    | GaussianMixtureParameters
    | BayesianMixtureParameters
    | AgglomerativeParameters
    | BirchParameters
    | MeanShiftParameters
    | SpectralClusteringParameters
    | AffinityPropagationParameters
    | SVDParameters
    | ICAParameters
    | FactorAnalysisParameters
    | KernelPCAParameters
    | NMFParameters
    | GaussianProjectionParameters
    | SparseProjectionParameters
    | IsomapParameters
    | MDSParameters
    | SpectralEmbeddingParameters
    | LLEParameters
)
EXTRA_DEFAULTS: dict[Algorithm, ExtraParameters] = {
    DBSCANParameters.algorithm: DBSCANParameters(),
    HDBSCANParameters.algorithm: HDBSCANParameters(),
    OPTICSParameters.algorithm: OPTICSParameters(),
    MiniBatchParameters.algorithm: MiniBatchParameters(),
    GaussianMixtureParameters.algorithm: GaussianMixtureParameters(),
    BayesianMixtureParameters.algorithm: BayesianMixtureParameters(),
    AgglomerativeParameters.algorithm: AgglomerativeParameters(),
    BirchParameters.algorithm: BirchParameters(),
    MeanShiftParameters.algorithm: MeanShiftParameters(),
    SpectralClusteringParameters.algorithm: SpectralClusteringParameters(),
    AffinityPropagationParameters.algorithm: AffinityPropagationParameters(),
    SVDParameters.algorithm: SVDParameters(),
    ICAParameters.algorithm: ICAParameters(),
    FactorAnalysisParameters.algorithm: FactorAnalysisParameters(),
    KernelPCAParameters.algorithm: KernelPCAParameters(),
    NMFParameters.algorithm: NMFParameters(),
    GaussianProjectionParameters.algorithm: GaussianProjectionParameters(),
    SparseProjectionParameters.algorithm: SparseProjectionParameters(),
    IsomapParameters.algorithm: IsomapParameters(),
    MDSParameters.algorithm: MDSParameters(),
    SpectralEmbeddingParameters.algorithm: SpectralEmbeddingParameters(),
    LLEParameters.algorithm: LLEParameters(),
}
EXTRA_LIMITS = {a: ALGORITHMS[a].row_limit for a in EXTRA_DEFAULTS}
EXTRA_DEFAULT_LIMITS = {a: ALGORITHMS[a].default_row_limit for a in EXTRA_DEFAULTS}
