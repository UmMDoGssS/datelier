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
[recorded evidence](evidence/package-layout/foundation.json).
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

Stage 3 passes: **28 application modules** moved into sessions, analysis,
exploration, tabular and media packages; import drafts join their existing import
controller family. Package APIs expose narrower state/controller families.
**123 focused tests** and **14 boundary/checkpoint tests** pass, including optional
Torch isolation and controller/rendering boundaries. The boundary audit now
recognizes whole-controller imports through the public sessions facade.
Pyrefly reports zero errors; Ruff and diff checks pass. The
[native workflow](evidence/package-layout/application.json) verifies sort,
undo/redo, literal-name selectors, explicit export/source protection and closure,
with no implicit analysis or playback.

Stage 4 passes: **72 GUI modules** grouped into input/layout/table/plot primitives,
modality context forms, distribution series, scatter/grid renderers, comparison
families and shell composition/layout/commands. Media pixel/texture primitives are
exported independently of the views that consume them. Scatter summary belongs
with scatter, so grid rendering does not participate in its import chain.
The large transform module is split into a shared base, row/column forms, value
forms and the contextual view; form classes and operation behavior are preserved.
**80 focused GUI/controller/boundary tests**, zero Pyrefly errors, Ruff and diff
checks pass. [Native step evidence](evidence/package-layout/gui.json) verifies
transforms, selectors, explicit export/closure and image/text/audio record views.
Whole-controller injection remains restricted to bootstrap and composition.

## Final ownership map

| Area | Cohesive packages and public API |
| --- | --- |
| Core | Dataset/revision/role/scalar and worker contracts in `core/__init__.py` |
| IO | `tabular`, `media`, `jobs`, annotation `readers`; existing array/checkpoint adapters |
| Pipeline and plotting | Typed `transforms`; `scatter`, `distributions`, `categories` |
| Workspace | `single`, `sessions`, `recipes`; recipe registry split into seven domain groups |
| Inspection | Column `profiles`; image `profiles`/`decoding`; audio `profiles`/`signal`/`decoding`; text `profiles`/`tokenizers`/`display`; annotation `association`/`profiles`/`overlay` |
| Application | `sessions`, `tabular`, `exploration`, `analysis`; media `audio`/`images`/`text`/`records`; source/import/annotation/comparison APIs |
| GUI | Shared `inputs`/`layout`/`tables`/`plots`; modality context forms and transform families; distribution/media profiles, scatter/grid renderers, comparison families, media primitives/views, shell composition/layout/commands |
| Analysis | Previously verified clustering/decomposition/manifold/projection methods and compatibility export packages |

Examples of public imports:

```python
from datelier.core import Dataset, DatasetRevision
from datelier.io.jobs import DatasetLoader
from datelier.pipeline.transforms import CastColumn
from datelier.inspection.images.profiles import ImageProfileSettings
from datelier.application.media.text import TextController
from datelier.gui.components.inputs import ColumnPicker, ChoiceField
from datelier.gui.components.tables import FactsTable
from datelier.gui.shell.composition import WorkbenchPage
```

Cross-package consumers use the public family API when it covers their needs.
Within a family, concrete imports describe dependencies without routing through
its initializer. Preparation/jobs and some higher-level views remain concrete
imports where a contract initializer must stay independent of its consumers.
Object navigation's dependency on session record views is now type-only.

The full-tree audit reviewed retained families as well. Core identity helpers,
array mapping/slicing, playback lifecycle/buffering, signal preparation, image
profile scans, comparison controllers, tabular adapters and recipe registration
already have a single responsibility within their packages. They retain cohesive
modules and narrow exports rather than nesting solely to meet a file-count limit.
Bootstrap/coordination roots stay small; feasibility probes retain their independent
fixed settings and original layout. The remaining broad import sets belong to
file coordination and GUI composition, where all immediate children are assembled.

## Final acceptance

[Verification](evidence/package-layout/verification.json) records **186 moved
modules**, **1,192 passing tests**, zero Pyrefly errors, passing Ruff lint/format
and whitespace checks. A [definition comparison](evidence/package-layout/bodies.json)
against `8fea1e4` matches **505 function/class bodies**, ignoring imports and
docstrings and matching split form classes by name. This guards preserved behavior;
it does not replace the behavioral/native tests.

The [source audit](evidence/package-layout/source-audit.json) inventories all
**537 source modules, 114 packages and 523 explicit re-exports**. Fresh processes
import domain modules and all production modules in forward/reverse order with
no ML or optional checkpoint runtimes; domain imports also avoid the GUI runtime.
The complete inventory, including feasibility probes, resolves in both orders.
The independent feasibility analysis probe retains its existing eager sklearn,
UMAP/Numba imports; production startup does not import that probe. Recipe kind
identifiers remain unique. [Import audit](evidence/package-layout/imports.json)
finds zero invalid or stale module references in source, tests and scripts.

[Wheel contents](evidence/package-layout/wheel-contents.json) exactly match the
source's Python module set. [Wheel import audit](evidence/package-layout/wheel-audit.json)
repeats the cold import checks from code extracted from the built wheel, with
isolated Python and each module's location asserted inside that extraction.
This checks packaging without reinstalling unchanged dependencies.

All **30 native harnesses** pass serially on Linux Mesa software OpenGL;
[commands, exits and logs](evidence/package-layout/native-acceptance.json) cover
analysis, annotations, audio, plot axes, browser/source/import flows, table/gallery,
text/image/audio records and profiles, comparisons, docking/splitters, numeric
sources, tab closure, transforms/export and separate-process restoration. A separate [all-method form check](evidence/package-layout/native-schemas.json)
passes for all 26 algorithms: native boolean/numeric/choice edits, conditional
visibility and automatic/manual draft retention; 381 frames, p95 14.934 ms, no
implicit analysis and original source bytes preserved. The
size/theme matrix was not repeated for this import/layout-only source change.
Resource benchmarks and their previous budgets retain their status; no new capacity
claims are made. Accelerated rendering, other platforms, human listening and
unfinished Titanic usability acceptance remain unchanged.

All package layout gates pass. Source-area links in the historical Titanic review
now point to current owners; its recorded observations remain historical.
