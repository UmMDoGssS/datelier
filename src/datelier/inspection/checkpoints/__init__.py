"""Prepare explicitly selected CPU tensor slices from checkpoint locators.

Headers and hierarchy remain distinct from value preparation. Slices retain
source coordinates and dtype provenance; bfloat16/float8 previews expose storage
bits alongside converted display values. Unsupported layouts remain diagnostic.
"""

from datelier.inspection.checkpoints.types import CheckpointCatalog as CheckpointCatalog
from datelier.inspection.checkpoints.types import TensorInfo as TensorInfo
