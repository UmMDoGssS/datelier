"""Timing, memory, responsiveness, and source-preservation measurements.

For example, run ``uv run python -m scripts.benchmarks.inspection`` with
POLARS_MAX_THREADS=8, or replace inspection with formats. Benchmarks
declare fixtures, scopes, sampling, and budgets in their owning modules. Some
drive native windows or create large temporary files. Interpret measured results
for their row/column widths, dtypes, hardware, and warm/cold process state;
retained cache bytes, process RSS, and driver VRAM are different quantities.
Historical reports are recoverable in Git, not new capacity/support guarantees.
"""
