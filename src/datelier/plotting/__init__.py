"""Prepared plots and linked selections, independent of native rendering.

Numeric distributions, category relationships, correlations, and raw/reduced
scatter carry explicit cohorts and source-row IDs. Plot coordinates use Float64,
so large integers/decimals may round; detailed values retain their source types.
Selection is bounded to 10,000 IDs, with full match counts where available.
Sampling, excluded values, overflow scaling, and truncation remain visible.
"""
