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
- [ ] Native column changes, exact corpus results and fresh-process selection restoration.
- [ ] Full-suite verification and final guidance/evidence review.

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
