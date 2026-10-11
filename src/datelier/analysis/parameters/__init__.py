"""Legacy method imports and bounded defaults, grouped by output family."""

from typing import cast, get_args

from datelier.analysis.algorithm import Algorithm
from datelier.analysis.algorithms import ALGORITHMS
from datelier.analysis.embedding_parameters import (
    EmbeddingParameters as EmbeddingParameters,
)
from datelier.analysis.embedding_parameters import (
    FactorAnalysisParameters as FactorAnalysisParameters,
)
from datelier.analysis.embedding_parameters import (
    GaussianProjectionParameters as GaussianProjectionParameters,
)
from datelier.analysis.embedding_parameters import (
    ICAParameters as ICAParameters,
)
from datelier.analysis.embedding_parameters import (
    IsomapParameters as IsomapParameters,
)
from datelier.analysis.embedding_parameters import (
    KernelPCAParameters as KernelPCAParameters,
)
from datelier.analysis.embedding_parameters import (
    LLEParameters as LLEParameters,
)
from datelier.analysis.embedding_parameters import (
    MDSParameters as MDSParameters,
)
from datelier.analysis.embedding_parameters import (
    NMFParameters as NMFParameters,
)
from datelier.analysis.embedding_parameters import (
    SparseProjectionParameters as SparseProjectionParameters,
)
from datelier.analysis.embedding_parameters import (
    SpectralEmbeddingParameters as SpectralEmbeddingParameters,
)
from datelier.analysis.embedding_parameters import (
    SVDParameters as SVDParameters,
)
from datelier.analysis.parameters.clustering import (
    AffinityPropagationParameters as AffinityPropagationParameters,
)
from datelier.analysis.parameters.clustering import (
    AgglomerativeParameters as AgglomerativeParameters,
)
from datelier.analysis.parameters.clustering import (
    BayesianMixtureParameters as BayesianMixtureParameters,
)
from datelier.analysis.parameters.clustering import (
    BirchParameters as BirchParameters,
)
from datelier.analysis.parameters.clustering import (
    ClusteringParameters as ClusteringParameters,
)
from datelier.analysis.parameters.clustering import (
    DBSCANParameters as DBSCANParameters,
)
from datelier.analysis.parameters.clustering import (
    GaussianMixtureParameters as GaussianMixtureParameters,
)
from datelier.analysis.parameters.clustering import (
    HDBSCANParameters as HDBSCANParameters,
)
from datelier.analysis.parameters.clustering import (
    MeanShiftParameters as MeanShiftParameters,
)
from datelier.analysis.parameters.clustering import (
    MiniBatchParameters as MiniBatchParameters,
)
from datelier.analysis.parameters.clustering import (
    OPTICSParameters as OPTICSParameters,
)
from datelier.analysis.parameters.clustering import (
    SpectralClusteringParameters as SpectralClusteringParameters,
)
from datelier.analysis.schema import validate_parameters as validate_parameters

ExtraParameters = ClusteringParameters | EmbeddingParameters
_EXTRA_TYPES = cast(tuple[type[ExtraParameters], ...], get_args(ExtraParameters))
EXTRA_DEFAULTS: dict[Algorithm, ExtraParameters] = {
    method.algorithm: method() for method in _EXTRA_TYPES
}
EXTRA_LIMITS = {a: ALGORITHMS[a].row_limit for a in EXTRA_DEFAULTS}
EXTRA_DEFAULT_LIMITS = {a: ALGORITHMS[a].default_row_limit for a in EXTRA_DEFAULTS}
