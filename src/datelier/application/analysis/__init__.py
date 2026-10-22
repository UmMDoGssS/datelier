"""Explicit analysis drafts, Run commands, and revision-bound result selection.

Coordinate methods use two/three components fixed by the chosen scatter view;
Colors methods fit the selected feature space independently. Settings changes
require another run. Completion retains the current route; Open result performs
navigation explicitly. Restoration installs settings without launching fitting.
"""

from datelier.application.analysis.controller import (
    AnalysisController as AnalysisController,
)
from datelier.application.analysis.settings import AnalysisSettings as AnalysisSettings
