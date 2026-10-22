"""Dataset identity, physical types, analysis roles, and bounded worker ownership.

Polars is the authoritative table representation. Source-row IDs live outside
user columns and survive sorting, filtering, sampling, and analysis. A revision
identifies one immutable table state; prepared results must match that revision
and their owning file/view before publication. These contracts have no GUI or
estimator dependencies.
"""

from datelier.core.column_roles import ColumnRole as ColumnRole
from datelier.core.column_roles import RoleInfo as RoleInfo
from datelier.core.dataset import Dataset as Dataset
from datelier.core.dataset import DatasetRevision as DatasetRevision
from datelier.core.dataset import SourceReference as SourceReference
from datelier.core.jobs import JobExecutor as JobExecutor
from datelier.core.jobs import SharedWorkers as SharedWorkers
from datelier.core.scalars import Scalar as Scalar
