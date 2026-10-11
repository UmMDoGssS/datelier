"""Legacy imports for concrete algorithm objects, without separate parameter records."""

from datelier.analysis.algorithm import Algorithm
from datelier.analysis.algorithms.affinity_propagation import (
    AffinityPropagationAlgorithm as AffinityPropagationParameters,
)
from datelier.analysis.algorithms.agglomerative import (
    AgglomerativeAlgorithm as AgglomerativeParameters,
)
from datelier.analysis.algorithms.bayesian_mixture import (
    BayesianMixtureAlgorithm as BayesianMixtureParameters,
)
from datelier.analysis.algorithms.birch import BirchAlgorithm as BirchParameters
from datelier.analysis.algorithms.dbscan import DBSCANAlgorithm as DBSCANParameters
from datelier.analysis.algorithms.factor_analysis import (
    FactorAnalysisAlgorithm as FactorAnalysisParameters,
)
from datelier.analysis.algorithms.gaussian_mixture import (
    GaussianMixtureAlgorithm as GaussianMixtureParameters,
)
from datelier.analysis.algorithms.gaussian_projection import (
    GaussianProjectionAlgorithm as GaussianProjectionParameters,
)
from datelier.analysis.algorithms.hdbscan import HDBSCANAlgorithm as HDBSCANParameters
from datelier.analysis.algorithms.ica import ICAAlgorithm as ICAParameters
from datelier.analysis.algorithms.isomap import IsomapAlgorithm as IsomapParameters
from datelier.analysis.algorithms.kernel_pca import (
    KernelPCAAlgorithm as KernelPCAParameters,
)
from datelier.analysis.algorithms.lle import LLEAlgorithm as LLEParameters
from datelier.analysis.algorithms.mds import MDSAlgorithm as MDSParameters
from datelier.analysis.algorithms.mean_shift import (
    MeanShiftAlgorithm as MeanShiftParameters,
)
from datelier.analysis.algorithms.mini_batch import (
    MiniBatchAlgorithm as MiniBatchParameters,
)
from datelier.analysis.algorithms.nmf import NMFAlgorithm as NMFParameters
from datelier.analysis.algorithms.optics import OPTICSAlgorithm as OPTICSParameters
from datelier.analysis.algorithms.registry import ALGORITHMS
from datelier.analysis.algorithms.sparse_projection import (
    SparseProjectionAlgorithm as SparseProjectionParameters,
)
from datelier.analysis.algorithms.spectral_clustering import (
    SpectralClusteringAlgorithm as SpectralClusteringParameters,
)
from datelier.analysis.algorithms.spectral_embedding import (
    SpectralEmbeddingAlgorithm as SpectralEmbeddingParameters,
)
from datelier.analysis.algorithms.svd import SVDAlgorithm as SVDParameters
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
