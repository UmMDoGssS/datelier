"""Annotated Pearson heatmaps and named pair grids using prepared shared cohorts.

Heatmaps show coefficients, finite-pair counts, an r color scale, and undefined
cells. Pair grids support up to eight features, share diagonal profile controls,
and navigate to a column profile or raw pair scatter. Scrollable chart regions
retain axis names and readable cells instead of clipping wide grids.
"""

from datelier.gui.relationships.grid.content import (
    CorrelationContent as CorrelationContent,
)
from datelier.gui.relationships.grid.correlations import (
    CorrelationPlot as CorrelationPlot,
)
from datelier.gui.relationships.grid.diagonals import CountDiagonal as CountDiagonal
from datelier.gui.relationships.grid.diagonals import DiagonalContent as DiagonalContent
from datelier.gui.relationships.grid.diagonals import distribution as distribution
from datelier.gui.relationships.grid.pairs import PairCell as PairCell
from datelier.gui.relationships.grid.pairs import PairGrid as PairGrid
