"""Header-first NumPy catalogs, lazy payload stores, and record mappings.

Aligned NPZ members open as columns with original first-axis positions as rows:
one-dimensional scalar members load in workers, higher-dimensional cells retain
lazy references. NPY, unequal lengths, or unsupported members use metadata views.
Confirmed mappings define record, display, channel, and supporting-field axes.
Object arrays requiring pickle remain diagnostic. ArrayStore leases bound
retention, using temporary storage for compressed or oversized members without
limiting the size of a selected inspectable member.
"""

from datelier.io.arrays.importing import load_arrays as load_arrays
from datelier.io.arrays.storage import ArrayStore as ArrayStore
