# Phase 12 — Text profiling and token inspection

Phase 11 is complete. Phase 12 is underway; M12.1–M12.2 pass. M12.3–M12.4
implementation, native, restoration and resource gates remain open.

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

## M12.1 — Native configuration and workspace recovery

The dockable Text panel exposes physical String field selection, inline versus
interpreted/external text, encoding, all five tokenizer modes, normalization,
case/whitespace/special-token count settings, and a current-table row position.
Single-record preparation and local JSON import/reload use shared workers and
explicit commands. The panel shows counted tokens, original code-point length,
source-row identity and decoding diagnostics. Whole-collection work and training
are not yet implemented. The small text preview is labeled at 4,096 code points;
full navigation and token highlighting remain M12.4 requirements.

Recipes persist settings and local artifact path/model/SHA-256, with legacy
defaults when absent. Restoration launches no text preparation, downloads or
training. A missing/changed tokenizer fails preparation with a reload action;
failed imports keep the prior recipe. Settings, revision, reference discovery
and file/view closure retire pending results. Count totals are prepared in the
worker, not rescanned during rendering.

Focused tokenization/worker/file/workspace tests: **28 passed**. The full suite:
**705 passed** in **19.58 s**, with three upstream checkpoint fixture warnings.
Pyrefly: **zero errors**, one existing suppression; Ruff lint/format
(**376 files**) and diff whitespace pass.

`LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 .venv/bin/python
scripts/text_tokenization_smoke.py --output docs/evidence/phase12` exercises native
mouse input for the normalization checkbox, explicit record preparation and
saved-artifact reload (**82 frames**). A separate process restores the saved BPE
recipe with no active text job, verifies missing-artifact failure, restores the
file, clicks reload and explicitly prepares the original record (**41 frames**).
[Native report](evidence/phase12/tokenizer-native.json) and
[restored panel](evidence/phase12/tokenizer-restore.png) retain the results.
The default GUI font lacks CJK/emoji coverage on this machine; multilingual
values/offsets are correct in behavioral fixtures, and native glyph coverage
must be established with M12.4 token-span rendering.

## M12.2 — Explicit selected-record local training

Text → Local tokenizer training exposes range, linked selection, seeded random
sample and all-current-row scopes, BPE/Unigram, vocabulary size, BPE minimum
frequency, Unigram piece length/pruning iterations/shrinking factor, special
tokens and a new local JSON output path. It uses the selected physical text
field/source/encoding and visible NFC/NFKC/lowercase settings; no imported
normalizer is silently included in training. The fixed pre-tokenizer uses
Unicode word/punctuation runs. Tokenizers exposes no training seed; the saved
artifact provides reproducible subsequent encoding. This is visible in controls.

Training starts only on **Train local tokenizer**. Shared workers read the chosen
records incrementally, report reading progress and label unavailable native
trainer progress. Null, empty and normalization/whitespace-only documents are
counted separately; decoding failures fail the command rather than hiding
unreadable inputs. The source fingerprint is checked before/after training.
Artifacts are complete tokenizer JSON plus `.provenance.json`, recording library
version, source fingerprint, file/view/revision, field, encoding, requested
source-row IDs, effective input digest, scope, normalization, trainer settings
and excluded outcomes. Workspaces reference both paths and SHA-256 values, not
training corpora. Reload validates their relationship and content identities.

Publication writes/fsyncs staged files and uses exclusive hard links, refusing
existing destinations even if created during training; failure removes only
the job's published files and temporary staging. Abandonment checks occur between
records and before/during publication. Executing native training can continue
until it returns, but cannot publish settings after abandonment/closure. Completed
unaccepted artifact cleanup uses a separate ownership scope on the same shared
scheduler so closing preparation cannot cancel its queued cleanup. Accepted
artifacts remain reusable local files. Failed training/import keeps the previous
tokenizer recipe; missing/changed artifacts require explicit recovery.

Focused training/tokenization/worker/editor-workspace checks: **26 passed**.
They cover both local models, selected-row provenance after reverse/filter,
known null/empty/tokenless outcomes, scope/seed identity, source preservation,
artifact/reference round trips, provenance mutation/removal, strict decoding
failures, no usable training documents, publication races, running abandonment
and completed unaccepted cleanup. The full suite: **713 passed** in **19.39 s**,
with three upstream checkpoint fixture warnings. Pyrefly: **zero errors**, one
existing suppression; Ruff lint/format (**381 files**) and diff whitespace pass.

`LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 .venv/bin/python
scripts/text_training_smoke.py --output docs/evidence/phase12` uses native mouse
commands to train BPE then Unigram (**77 frames**) on source rows **0,2,3**,
including one null and one empty record while excluding row 1. A separate process
restores the Unigram configuration/selection and provenance references, verifies
no implicit job, and explicitly tokenizes the original record (**13 frames**).
[Training report](evidence/phase12/training-native.json) and
[native controls](evidence/phase12/training-controls.png) preserve the evidence.

## M12.3 — Exact statistical foundation

Worker-callable `calculate_profile` calculates exact scoped token/document
frequencies keyed by piece/ID, vocabulary size, hapax counts and both
vocabulary/token hapax ratios, type-token ratio and Shannon entropy in bits.
It retains complete Polars record-length/outcome and frequency tables; display
histograms convert only prepared scalar lengths to NumPy. Null/failed documents
are excluded from length statistics; empty decoded documents are included,
respecting special-token counting. Original and normalized code-point totals
are distinct. Token and original-character length summaries use population
standard deviation and linear quantiles at 0/25/50/75/95/99/100 percent.
No-event ratios/entropy and no-document lengths are explicitly undefined.

Hand-calculated fixtures verify `a a b`, `b c`, empty, null and `a`: six tokens,
three vocabulary types, one hapax, type-token ratio 0.5, original source identity,
token/document frequencies and exact length/entropy outcomes. Additional
fixtures verify no records, strict decoding failure versus zero-length documents,
abandonment and counted/uncounted inserted specials. Focused text checks:
**22 passed**. Pyrefly zero errors; Ruff lint/format and diff whitespace pass.
This preparation foundation introduces no GUI behavior. M12.3 remains open
until worker publication, native displays and corpus resources pass.
