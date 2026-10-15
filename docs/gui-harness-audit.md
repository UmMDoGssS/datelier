# GUI acceptance harness audit

The retained tools were grouped into repository-only packages on 2026-10-15.
Use [the development tool guide](../scripts/README.md) for current commands.
The source links below point to the grouped modules; historical names and
recorded evidence retain their original meaning.

The fresh GUI replacement removed the widget/session APIs used by 79 legacy
native smoke harnesses. These harnesses are retired from the active script inventory;
all behavioral tests and domain/resource benchmarks remain. The Unicode font
harness is migrated unchanged in substance to `scripts/gui/fonts.py`.

The per-harness purposes and concrete replacement native scripts/tests are recorded
in [harness-migration.json](evidence/gui-overhaul/harness-migration.json). This is
capability coverage, not a claim that every historical click sequence was replayed.
New native harnesses use scoped probes and controller commands rather than patches
to removed widgets. Historical phase documents and evidence retain their original
meaning; their retired command examples must be run against the historical code.

Every retired source can be recovered from the pre-retirement commit:

```bash
git show 9a6a808:scripts/<retired-name>.py > /tmp/<retired-name>.py
```

To execute that historical harness, use its matching pre-overhaul checkout
(`13c0e58`), not the rebuilt package. The saved incremental branch and stash
documented in [gui-overhaul.md](gui-overhaul.md) remain intact.

| Capability | Current native / resource gates | Behavioral coverage |
| --- | --- | --- |
| Analysis and scatter | [analysis.py](../scripts/gui/analysis.py), [scatter.py](../scripts/gui/scatter.py), [analysis_gui.py](../scripts/benchmarks/analysis_gui.py), [exploration.py](../scripts/benchmarks/exploration.py) | [test_analysis_jobs.py](../tests/test_analysis_jobs.py), [test_rebuild_scatter.py](../tests/test_rebuild_scatter.py), [test_scatter3d.py](../tests/test_scatter3d.py), [test_selection.py](../tests/test_selection.py) |
| Image, annotations and references | [annotations.py](../scripts/gui/annotations.py), [image_profiles.py](../scripts/gui/image_profiles.py), [image_comparisons.py](../scripts/gui/image_comparisons.py), [table.py](../scripts/gui/table.py), [records.py](../scripts/gui/records.py), [box_overlays.py](../scripts/benchmarks/box_overlays.py), [references.py](../scripts/benchmarks/references.py) | [test_rebuild_annotations.py](../tests/test_rebuild_annotations.py), [test_rebuild_images.py](../tests/test_rebuild_images.py), [test_references.py](../tests/test_references.py) |
| Structured, array and checkpoint sources | [sources.py](../scripts/gui/sources.py), [numeric.py](../scripts/gui/numeric.py), [gallery.py](../scripts/gui/gallery.py), [objects.py](../scripts/benchmarks/objects.py), [arrays.py](../scripts/benchmarks/arrays.py), [checkpoints.py](../scripts/benchmarks/checkpoints.py) | [test_rebuild_sources.py](../tests/test_rebuild_sources.py), [test_npz_aligned_records.py](../tests/test_npz_aligned_records.py), [test_array_record_sessions.py](../tests/test_array_record_sessions.py) |
| Audio inspection and comparison | [audio.py](../scripts/gui/audio.py), [audio_comparisons.py](../scripts/gui/audio_comparisons.py), [records.py](../scripts/gui/records.py), [media_matrix.py](../scripts/gui/media_matrix.py), [audio_views.py](../scripts/benchmarks/audio_views.py), [audio_playback.py](../scripts/benchmarks/audio_playback.py) | [test_rebuild_audio.py](../tests/test_rebuild_audio.py), [test_audio_playback.py](../tests/test_audio_playback.py) |
| Profiles, relationships and interpretations | [categories.py](../scripts/gui/categories.py), [pairs.py](../scripts/gui/pairs.py), [axes.py](../scripts/gui/axes.py), [workbench.py](../scripts/gui/workbench.py), [media_matrix.py](../scripts/gui/media_matrix.py) | [test_rebuild_plot_controls.py](../tests/test_rebuild_plot_controls.py), [test_rebuild_relationships.py](../tests/test_rebuild_relationships.py), [test_column_roles.py](../tests/test_column_roles.py), [test_nested_columns.py](../tests/test_nested_columns.py) |
| Comparisons | [comparisons.py](../scripts/gui/comparisons.py), [text_comparisons.py](../scripts/gui/text_comparisons.py), [image_comparisons.py](../scripts/gui/image_comparisons.py), [audio_comparisons.py](../scripts/gui/audio_comparisons.py), [comparisons.py](../scripts/benchmarks/comparisons.py) | [test_rebuild_comparisons.py](../tests/test_rebuild_comparisons.py) |
| Loading, recovery, sessions, shell and persistence | [browser.py](../scripts/gui/browser.py), [imports.py](../scripts/gui/imports.py), [tabs.py](../scripts/gui/tabs.py), [pending_views.py](../scripts/gui/pending_views.py), [workspace.py](../scripts/gui/workspace.py), [layout_restore.py](../scripts/gui/layout_restore.py) | [test_editor_sessions.py](../tests/test_editor_sessions.py), [test_rebuild_controllers.py](../tests/test_rebuild_controllers.py), [test_multimodal_sessions.py](../tests/test_multimodal_sessions.py) |
| Operations and export | [workflow.py](../scripts/gui/workflow.py), [imports.py](../scripts/gui/imports.py), [operations.py](../scripts/benchmarks/operations.py), [exploration.py](../scripts/benchmarks/exploration.py) | [test_editing.py](../tests/test_editing.py), [test_exporting.py](../tests/test_exporting.py), [test_transforms.py](../tests/test_transforms.py) |
| Table and gallery inspection | [table.py](../scripts/gui/table.py), [records.py](../scripts/gui/records.py), [references.py](../scripts/benchmarks/references.py), [inspection.py](../scripts/benchmarks/inspection.py) | [test_records.py](../tests/test_records.py), [test_table_presentation.py](../tests/test_table_presentation.py) |
| Text inspection, profiles, training and comparison | [text_profiles.py](../scripts/gui/text_profiles.py), [text_comparisons.py](../scripts/gui/text_comparisons.py), [records.py](../scripts/gui/records.py), [table.py](../scripts/gui/table.py), [text_profiles.py](../scripts/benchmarks/text_profiles.py), [text_inspection.py](../scripts/benchmarks/text_inspection.py) | [test_rebuild_text_profiles.py](../tests/test_rebuild_text_profiles.py), [test_text_tokenization.py](../tests/test_text_tokenization.py), [test_rebuild_text_comparisons.py](../tests/test_rebuild_text_comparisons.py) |
| Sizing and docking | [workbench.py](../scripts/gui/workbench.py), [media_matrix.py](../scripts/gui/media_matrix.py), [docking.py](../scripts/gui/docking.py), [splitter.py](../scripts/gui/splitter.py) | [test_column_selection_policies.py](../tests/test_column_selection_policies.py), [test_rebuild_controllers.py](../tests/test_rebuild_controllers.py) |
| Unicode fonts | [fonts.py](../scripts/gui/fonts.py) | Direct native glyph presence, baking and visible emoji bounds |

The audio gate uses deterministic injected output to verify native commands and
lifecycle. Actual human listening remains deferred by the user; retiring the old
listening harness does not close that assumption. Titanic human usability gates,
accelerated rendering and other platforms retain their previous status.

Run the current native inventory serially (a Linux display is required):

```bash
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run python -m scripts.gui.acceptance --matrix
```

Use `--resume` to continue an interrupted run with the same output directory;
the runner validates its saved command list before skipping successful cases.
The runner records each command, exit status, duration and complete log under
`/tmp/datelier-native-acceptance`. `--matrix` adds both shell and media checks for
all nine size/theme combinations. Resource benchmarks retain separate commands
and declared budgets; [gui-overhaul.md](gui-overhaul.md) records their evidence.
