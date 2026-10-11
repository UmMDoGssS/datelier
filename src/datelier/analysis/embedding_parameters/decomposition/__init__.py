"""Legacy decomposition names are aliases to executable methods."""

from datelier.analysis.algorithms.decomposition import (
    FactorAnalysisAlgorithm as FactorAnalysisParameters,
)
from datelier.analysis.algorithms.decomposition import (
    ICAAlgorithm as ICAParameters,
)
from datelier.analysis.algorithms.decomposition import (
    KernelPCAAlgorithm as KernelPCAParameters,
)
from datelier.analysis.algorithms.decomposition import (
    NMFAlgorithm as NMFParameters,
)
from datelier.analysis.algorithms.decomposition import (
    SVDAlgorithm as SVDParameters,
)

DecompositionParameters = (
    SVDParameters
    | ICAParameters
    | FactorAnalysisParameters
    | KernelPCAParameters
    | NMFParameters
)
