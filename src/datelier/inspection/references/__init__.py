"""Resolve local references without rewriting the original cell value.

Resolution tries exact absolute/source-relative paths before unambiguous names
or stems under configured nearby roots. Ambiguous/missing matches need an explicit
choice. Discovery and decoding run in workers; CPU previews are bounded and GPU
textures belong to the file's GUI owner. Direct media manifests resolve their
own paths without nearby discovery.
"""

from datelier.inspection.references.types import AssetIdentity as AssetIdentity
from datelier.inspection.references.types import AssetPreview as AssetPreview
from datelier.inspection.references.types import ReferenceMapping as ReferenceMapping
from datelier.inspection.references.types import ReferenceSettings as ReferenceSettings
from datelier.inspection.references.types import Resolution as Resolution
