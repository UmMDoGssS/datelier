# Codebase package layout

The 2026-10-11 clarification extends public package exports beyond analysis.
Implementation proceeds in separately verified domain, inspection, application
and GUI stages. Existing numerical algorithms and recipe class names remain
unchanged. Import and source-path moves are recorded in
[evidence/package-layout/moves.json](evidence/package-layout/moves.json).

## Scope and sequence

1. Group tabular/media adapters; single-source and session persistence; recipe
   serialization; typed transforms; distributions, categories and scatter prep.
2. Group image collection profiling and decoding, audio statistics and signal
   views, text corpus/tokenization/display, and annotation association/profile/scene.
3. Group application analysis/plot state, media controllers, table state and
   editor-session orchestration; reuse the existing source/import/comparison groups.
4. Group GUI form inputs, layout, tables and plot components; context forms by
   modality and operation; profile/relationship/comparison drawing families and
   shell composition.
5. Audit every package, stale references and wheel contents; verify all tests,
   types/lint and native analysis, source, media, comparison and restoration paths.

Initializers explicitly export cohesive APIs. Parent packages should not eagerly
load all descendants; worker lifecycles, codec/device runtimes and GUI bootstrap
remain concrete dependencies when needed to avoid cycles or initialization side
effects. Do not introduce wildcard imports, dynamic import routers or wrappers.
Small packages that already have one responsibility need no artificial nesting.

## Verification

Stage 1 passes: 30 modules moved; codec record registration split into seven
trusted domain groups. **322 focused tests** pass, covering import formats,
source protection, transform/history invariants, plots, all algorithm recipes and
workspace restoration. Pyrefly: zero errors (one existing suppression, 37 existing
warnings). Ruff lint/format and whitespace checks pass. Separate-process native
save/restore passes with original source bytes preserved and zero implicit work;
[recorded evidence](evidence/package-layout/foundation.json). Stage 2 is next.
Existing analysis package verification remains valid.

Stage 2 passes: **49 inspection modules** moved into profile, decoding, signal,
tokenizer, display, association and overlay packages; contract exports keep recipe
imports independent of preparation/jobs. **403 focused tests**, zero Pyrefly errors,
Ruff and diff checks pass. [Native record evidence](evidence/package-layout/inspection.json)
verifies original image pixels, Unicode token spans and original audio waveforms,
source preservation and zero implicit collection work/playback.

The original record harness requested text preparation before background reference
discovery completed. The later reference-index change correctly invalidated its
result. The same failure was reproduced against the preceding commit `bf018ec`;
the harness now waits for preferences/reference discovery before its explicit
command. Application cancellation and publication behavior were unchanged.
