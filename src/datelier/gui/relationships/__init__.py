"""Separate 2D/3D scatter, category/value distributions, and grouped count charts.

Coordinate and Colors sources are independent and contextual: columns show axis
pickers, reductions show their explicit Run form, clustering shows color fitting.
Box/violin use Category plus numeric Value; grouped counts require a distinct
categorical Group by. Single-column counts route to Profiles. Saved legacy count
views migrate there; former aggregate bars migrate to Box with their columns.
"""
