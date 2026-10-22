"""Virtualized prepared table pages, source-row selection, and cell presentation.

Only visible rows/columns draw; worker pages format bounded previews. Full values
remain available in Inspect. Numeric shading supports percentile, min/max, and
custom ranges; categorical colors are stable. Null, nonfinite, outside-range,
and constant values have distinct markers. Selections use source IDs independent
of sort/filter display positions and survive exclusion from a plot sample.
"""

from datelier.gui.table.view import TableView as TableView
