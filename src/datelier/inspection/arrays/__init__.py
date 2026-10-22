"""Exact array slices, record mappings, and display-only preparation.

Selected axes, fixed coordinates, and windows retain original member indices.
Vectors, matrices, images, and waveform mappings share source locators; a record
mapping must be confirmed and aligned supporting fields must have matching row
counts. Heatmap ranges/colormaps affect display buffers, never original values.
Saved mappings and slices describe work to prepare without embedding payloads.
"""

from datelier.inspection.arrays.mapping import ArrayLayout as ArrayLayout
from datelier.inspection.arrays.mapping import ArrayRecordMapping as ArrayRecordMapping
from datelier.inspection.arrays.mapping import MappingSuggestion as MappingSuggestion
from datelier.inspection.arrays.mapping import SupportingArray as SupportingArray
from datelier.inspection.arrays.mapping import suggest_mapping as suggest_mapping
from datelier.inspection.arrays.types import ArrayCatalog as ArrayCatalog
from datelier.inspection.arrays.types import ArrayMember as ArrayMember
