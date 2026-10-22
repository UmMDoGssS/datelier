"""Worker-local tokenization and explicit source-preserving BPE/Unigram training.

Tokenizer JSON is local: no model downloads or implicit training. Training writes
a new artifact and provenance sidecar with source hashes, selected row/element
identities, settings, and exclusions. Existing destinations are refused. Saved
artifact fingerprints support explicit missing/changed-artifact recovery.
"""

from datelier.inspection.text.tokenizers.tokenization import (
    TextTokenizer as TextTokenizer,
)
from datelier.inspection.text.tokenizers.tokenization import (
    canonical_steps as canonical_steps,
)
from datelier.inspection.text.tokenizers.tokenization import (
    import_tokenizer as import_tokenizer,
)
from datelier.inspection.text.tokenizers.tokenization import (
    normalization as normalization,
)
from datelier.inspection.text.tokenizers.tokenization import source_span as source_span
