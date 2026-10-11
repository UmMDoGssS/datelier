"""Legacy imports for concrete algorithm objects, without separate parameter records."""

from datelier.analysis.algorithm import Algorithm
from datelier.analysis.algorithms import ALGORITHMS
from datelier.analysis.algorithms.decomposition import (
    FactorAnalysisAlgorithm as FactorAnalysisParameters,
)
from datelier.analysis.algorithms.decomposition import ICAAlgorithm as ICAParameters
from datelier.analysis.algorithms.decomposition import (
    KernelPCAAlgorithm as KernelPCAParameters,
)
from datelier.analysis.algorithms.decomposition import NMFAlgorithm as NMFParameters
from datelier.analysis.algorithms.decomposition import SVDAlgorithm as SVDParameters
from datelier.analysis.algorithms.manifold import IsomapAlgorithm as IsomapParameters
from datelier.analysis.algorithms.manifold import LLEAlgorithm as LLEParameters
from datelier.analysis.algorithms.manifold import MDSAlgorithm as MDSParameters
from datelier.analysis.algorithms.manifold import (
    SpectralEmbeddingAlgorithm as SpectralEmbeddingParameters,
)
from datelier.analysis.algorithms.projection import (
    GaussianProjectionAlgorithm as GaussianProjectionParameters,
)
from datelier.analysis.algorithms.projection import (
    SparseProjectionAlgorithm as SparseProjectionParameters,
)

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
