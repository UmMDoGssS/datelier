"""Legacy clustering names are aliases to executable methods."""

from datelier.analysis.algorithms.clustering import (
    AffinityPropagationAlgorithm as AffinityPropagationParameters,
)
from datelier.analysis.algorithms.clustering import (
    AgglomerativeAlgorithm as AgglomerativeParameters,
)
from datelier.analysis.algorithms.clustering import (
    BayesianMixtureAlgorithm as BayesianMixtureParameters,
)
from datelier.analysis.algorithms.clustering import (
    BirchAlgorithm as BirchParameters,
)
from datelier.analysis.algorithms.clustering import (
    DBSCANAlgorithm as DBSCANParameters,
)
from datelier.analysis.algorithms.clustering import (
    GaussianMixtureAlgorithm as GaussianMixtureParameters,
)
from datelier.analysis.algorithms.clustering import (
    HDBSCANAlgorithm as HDBSCANParameters,
)
from datelier.analysis.algorithms.clustering import (
    MeanShiftAlgorithm as MeanShiftParameters,
)
from datelier.analysis.algorithms.clustering import (
    MiniBatchAlgorithm as MiniBatchParameters,
)
from datelier.analysis.algorithms.clustering import (
    OPTICSAlgorithm as OPTICSParameters,
)
from datelier.analysis.algorithms.clustering import (
    SpectralClusteringAlgorithm as SpectralClusteringParameters,
)

ClusteringParameters = (
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
)
