"""Compatibility exports; parameter definitions live with concrete algorithms."""

from datelier.analysis.algorithm import Algorithm
from datelier.analysis.algorithms.affinitypropagation import (
    AffinityPropagationParameters as AffinityPropagationParameters,
)
from datelier.analysis.algorithms.agglomerative import (
    AgglomerativeParameters as AgglomerativeParameters,
)
from datelier.analysis.algorithms.bayesianmixture import (
    BayesianMixtureParameters as BayesianMixtureParameters,
)
from datelier.analysis.algorithms.birch import BirchParameters as BirchParameters
from datelier.analysis.algorithms.dbscan import DBSCANParameters as DBSCANParameters
from datelier.analysis.algorithms.factoranalysis import (
    FactorAnalysisParameters as FactorAnalysisParameters,
)
from datelier.analysis.algorithms.gaussianmixture import (
    GaussianMixtureParameters as GaussianMixtureParameters,
)
from datelier.analysis.algorithms.gaussianprojection import (
    GaussianProjectionParameters as GaussianProjectionParameters,
)
from datelier.analysis.algorithms.hdbscan import HDBSCANParameters as HDBSCANParameters
from datelier.analysis.algorithms.ica import ICAParameters as ICAParameters
from datelier.analysis.algorithms.isomap import IsomapParameters as IsomapParameters
from datelier.analysis.algorithms.kernelpca import (
    KernelPCAParameters as KernelPCAParameters,
)
from datelier.analysis.algorithms.lle import LLEParameters as LLEParameters
from datelier.analysis.algorithms.mds import MDSParameters as MDSParameters
from datelier.analysis.algorithms.meanshift import (
    MeanShiftParameters as MeanShiftParameters,
)
from datelier.analysis.algorithms.minibatch import (
    MiniBatchParameters as MiniBatchParameters,
)
from datelier.analysis.algorithms.nmf import NMFParameters as NMFParameters
from datelier.analysis.algorithms.optics import OPTICSParameters as OPTICSParameters
from datelier.analysis.algorithms.registry import BUILDERS
from datelier.analysis.algorithms.sparseprojection import (
    SparseProjectionParameters as SparseProjectionParameters,
)
from datelier.analysis.algorithms.spectralclustering import (
    SpectralClusteringParameters as SpectralClusteringParameters,
)
from datelier.analysis.algorithms.spectralembedding import (
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
EXTRA_LIMITS = {a: BUILDERS[a].row_limit for a in EXTRA_DEFAULTS}
EXTRA_DEFAULT_LIMITS = {a: BUILDERS[a].default_row_limit for a in EXTRA_DEFAULTS}
