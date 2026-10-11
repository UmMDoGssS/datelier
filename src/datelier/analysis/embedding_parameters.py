"""Compatibility exports; parameter definitions live with concrete algorithms."""

from datelier.analysis.algorithm import Algorithm
from datelier.analysis.algorithms.factor_analysis import (
    FactorAnalysisParameters as FactorAnalysisParameters,
)
from datelier.analysis.algorithms.gaussian_projection import (
    GaussianProjectionParameters as GaussianProjectionParameters,
)
from datelier.analysis.algorithms.ica import ICAParameters as ICAParameters
from datelier.analysis.algorithms.isomap import IsomapParameters as IsomapParameters
from datelier.analysis.algorithms.kernel_pca import (
    KernelPCAParameters as KernelPCAParameters,
)
from datelier.analysis.algorithms.lle import LLEParameters as LLEParameters
from datelier.analysis.algorithms.mds import MDSParameters as MDSParameters
from datelier.analysis.algorithms.nmf import NMFParameters as NMFParameters
from datelier.analysis.algorithms.registry import ALGORITHMS
from datelier.analysis.algorithms.sparse_projection import (
    SparseProjectionParameters as SparseProjectionParameters,
)
from datelier.analysis.algorithms.spectral_embedding import (
    SpectralEmbeddingParameters as SpectralEmbeddingParameters,
)
from datelier.analysis.algorithms.svd import SVDParameters as SVDParameters

EmbeddingParameters = (
    SVDParameters
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
EMBEDDING_DEFAULTS: dict[Algorithm, EmbeddingParameters] = {
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
EMBEDDING_LIMITS = {a: ALGORITHMS[a].row_limit for a in EMBEDDING_DEFAULTS}
