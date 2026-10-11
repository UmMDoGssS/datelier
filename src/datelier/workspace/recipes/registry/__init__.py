"""Finite recipe catalog composed from domain-owned record groups."""

from datelier.workspace.recipes.registry.analysis import RECORDS as ANALYSIS_RECORDS
from datelier.workspace.recipes.registry.annotations import (
    RECORDS as ANNOTATIONS_RECORDS,
)
from datelier.workspace.recipes.registry.audio import RECORDS as AUDIO_RECORDS
from datelier.workspace.recipes.registry.images import RECORDS as IMAGES_RECORDS
from datelier.workspace.recipes.registry.tabular import RECORDS as TABULAR_RECORDS
from datelier.workspace.recipes.registry.text import RECORDS as TEXT_RECORDS
from datelier.workspace.recipes.registry.workspace import RECORDS as WORKSPACE_RECORDS

RECORDS = (
    *ANALYSIS_RECORDS,
    *ANNOTATIONS_RECORDS,
    *AUDIO_RECORDS,
    *IMAGES_RECORDS,
    *TEXT_RECORDS,
    *TABULAR_RECORDS,
    *WORKSPACE_RECORDS,
)
