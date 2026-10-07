# Text inspection within Profiles

The requested navigation change moves the Text panel into **Explore → Profiles**.
The shared **Columns** checklist includes all physical String fields, including
text and external-text interpretations. Selecting one shows tokenizer/source
settings, explicit corpus profiling and local training, exact statistics and the
complete record/token preview. String categories keep **Counts** by default and
can choose **Text tokens** without changing the dataset interpretation. Numeric
multi-selection and date/category views retain their existing behavior.

## Verification steps

- [x] Selection, routing, workspace recipe support and panel integration.
- [x] Native column changes, exact corpus results and fresh-process selection restoration.
- [x] Full-suite verification and final guidance/evidence review.

The first step passes 83 focused selection, profile, text worker, workspace and
preference tests. Pyrefly reports zero errors; Ruff lint and formatting pass.
The adapted native tokenizer smoke test exercises controls, original Unicode
spans, missing-artifact recovery and explicit preparation within Explore →
Profiles: 82 save frames and 41 fresh-process reopen frames. No text jobs start
implicitly on reopen. The standalone Text dockable window is removed; tokenizer
configuration and computed results remain owned by each independent file/view.

Selected profile fields and the String category **Text tokens** choice persist
as workspace recipes. Corpus calculations, training and record preparation still
require explicit commands. Old layouts may contain a saved Text window entry;
they continue loading the existing Explore dock without registering that panel.

## Final acceptance

`scripts/text_profile_navigation_smoke.py` uses native mouse input to select
text through the shared checklist, calculate its exact corpus profile, return to
a numeric profile, switch a String category from Counts to Text tokens and
choose another text field. The fixtures produce 6 tokens / 5 vocabulary types,
3 / 2 and 4 / 4 respectively. Changing text fields removes the prior field's
result and requires a new calculation. Category interpretation remains intact.

The save run passes in **536 frames**. An independent process reopens in **59
frames**, retaining the selected text column and category text-view preference,
with no record/profile/training jobs running before an explicit command. It
also loads a layout containing an obsolete Text window entry; Explore remains
usable and no standalone Text window is registered. Source hashes are unchanged.
[Native results](evidence/text-profiles-navigation/profiles-native.json),
[selected-field screenshot](evidence/text-profiles-navigation/profiles-text.png)
and [reopened screenshot](evidence/text-profiles-navigation/profiles-restored.png)
record the acceptance run.

The adapted native local-training check also passes both BPE and Unigram on
selected source rows 0/2/3: **78 save frames**, **13 reopen frames**, with no
implicit training. [Training results](evidence/text-profiles-navigation/training-native.json)
and [tokenizer control results](evidence/text-profiles-navigation/tokenizer-native.json)
record these checks.

A GUI-independent two-file workspace test additionally verifies independent
text/profile choices and no implicit text work during restoration. The full
suite passes **739 tests** (3 existing upstream checkpoint warnings). Pyrefly reports **0 errors** with the existing suppression/warnings;
Ruff lint and formatting pass. Native rendering was checked on Linux with Mesa
software OpenGL; the existing Phase 12 resource and platform limits still apply.
