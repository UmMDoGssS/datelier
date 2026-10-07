# Phase 12 — Text profiling and token inspection

Phase 11 is complete. Phase 12 is underway; M12.1–M12.4 exit gates remain
open until their native, restoration, full-suite and resource evidence passes.

## Delivery steps

1. Establish the Linux/Python 3.14 Tokenizers dependency and typed, source-aware
   text reads and tokenization with original offsets.
2. Add worker-owned tokenizer configuration and native controls, local imports,
   saved recipes and explicit missing/changed-artifact recovery (M12.1).
3. Add explicit selected-record BPE/Unigram training, safe abandonment, atomic
   local artifacts and input/settings provenance (M12.2).
4. Calculate exact corpus statistics in workers and render bounded distributions
   and frequency views with explicit corpus scope (M12.3).
5. Add full-text/token navigation and highlighting in Inspect, then shared
   tokenizer cross-file text comparisons, workspace restoration and measured
   corpus/inspection resources (M12.4).

Each coherent implementation step is checked and committed before the next.
Milestone completion requires the full suite and its listed acceptance gates.

## Dependency and source-preserving foundation

`uv add 'tokenizers>=0.22,<1'` resolves **Tokenizers 0.23.2**, verified on
Linux x86_64/Python **3.14.7**. Local BPE and Unigram training/encoding probes
handle `tiếng Việt 中 🙂` without downloads. The version bound retains the
verified API family; no Hub method is used by the application.

Worker-only text reads retain file/revision/source-row/field identities and
distinguish null, empty, ready and decoding/reference errors. External files use
explicit strict encoding (UTF-8 by default) and record path/SHA-256. Reads reject
assets changing during preparation. The original table and files are preserved.

Units are Unicode code points after visible normalization for Character;
non-whitespace runs for Whitespace; Unicode word runs and punctuation runs for
Word (Tokenizers `Whitespace`, not language-specific segmentation). Character
whitespace can be excluded. BPE/Unigram pieces/IDs follow the referenced local
JSON. Configured NFC/NFKC and lowercase precede an imported normalizer; imported
padding/truncation and stochastic BPE dropout are disabled for complete,
reproducible inspection. Added special tokens and counting them are independent
settings. Offsets are half-open indices into the **original Python string**;
composed spans include original trailing combining marks, and normalization
expansion may give multiple pieces the same source span. Inserted special tokens
have no source span.

`tests/test_text_tokenization.py`: **8 passed**, covering multilingual units,
emoji/newlines, composed accents/compatibility expansion, null/empty/strict
decoding errors, row alignment, BPE/Unigram local round trips, special counts,
complete encoding despite imported truncation/padding, changed/missing artifacts
and physical String eligibility. Pyrefly reports zero errors (one existing
suppression). Ruff lint/format and diff whitespace pass. This foundation does
not introduce GUI behavior; native controls and recovery remain outstanding.
