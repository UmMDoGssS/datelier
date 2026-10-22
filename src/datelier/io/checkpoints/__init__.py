"""Optional restricted CPU checkpoint inspection with lazy PyTorch imports.

Primitive hierarchies and tensor metadata open first; selected dense tensor
values are prepared explicitly. The ``checkpoints`` extra supplies CPU PyTorch.
Custom objects, sparse/quantized layouts, and unsupported containers remain
diagnostic; inspection never constructs models or runs inference.
"""

from datelier.io.checkpoints.importing import load_checkpoint as load_checkpoint
