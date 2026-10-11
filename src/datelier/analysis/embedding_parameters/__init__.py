"""Legacy embedding imports; aliases share the executable method classes."""

from typing import cast, get_args

from datelier.analysis.algorithm import Algorithm
from datelier.analysis.algorithms import ALGORITHMS
from datelier.analysis.embedding_parameters.decomposition import (
    DecompositionParameters as DecompositionParameters,
)
from datelier.analysis.embedding_parameters.decomposition import (
    FactorAnalysisParameters as FactorAnalysisParameters,
)
from datelier.analysis.embedding_parameters.decomposition import (
    ICAParameters as ICAParameters,
)
from datelier.analysis.embedding_parameters.decomposition import (
    KernelPCAParameters as KernelPCAParameters,
)
from datelier.analysis.embedding_parameters.decomposition import (
    NMFParameters as NMFParameters,
)
from datelier.analysis.embedding_parameters.decomposition import (
    SVDParameters as SVDParameters,
)
from datelier.analysis.embedding_parameters.manifold import (
    IsomapParameters as IsomapParameters,
)
from datelier.analysis.embedding_parameters.manifold import (
    LLEParameters as LLEParameters,
)
from datelier.analysis.embedding_parameters.manifold import (
    ManifoldParameters as ManifoldParameters,
)
from datelier.analysis.embedding_parameters.manifold import (
    MDSParameters as MDSParameters,
)
from datelier.analysis.embedding_parameters.manifold import (
    SpectralEmbeddingParameters as SpectralEmbeddingParameters,
)
from datelier.analysis.embedding_parameters.projection import (
    GaussianProjectionParameters as GaussianProjectionParameters,
)
from datelier.analysis.embedding_parameters.projection import (
    ProjectionParameters as ProjectionParameters,
)
from datelier.analysis.embedding_parameters.projection import (
    SparseProjectionParameters as SparseProjectionParameters,
)

EmbeddingParameters = (
    DecompositionParameters | ProjectionParameters | ManifoldParameters
)
_EMBEDDING_TYPES = cast(
    tuple[type[EmbeddingParameters], ...], get_args(EmbeddingParameters)
)
EMBEDDING_DEFAULTS: dict[Algorithm, EmbeddingParameters] = {
    method.algorithm: method() for method in _EMBEDDING_TYPES
}
EMBEDDING_LIMITS = {a: ALGORITHMS[a].row_limit for a in EMBEDDING_DEFAULTS}
