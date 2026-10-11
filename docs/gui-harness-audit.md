# GUI acceptance harness audit

The fresh GUI replacement removed the widget/session APIs used by 79 legacy
native smoke harnesses. These harnesses are retired from the active script inventory;
all behavioral tests and domain/resource benchmarks remain. The Unicode font
harness is migrated unchanged in substance to `scripts/rebuild_fonts_smoke.py`.

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
| Analysis and scatter | [rebuild_analysis_smoke.py](../scripts/rebuild_analysis_smoke.py), [rebuild_scatter_smoke.py](../scripts/rebuild_scatter_smoke.py), [benchmark_analysis_gui.py](../scripts/benchmark_analysis_gui.py), [benchmark_exploration.py](../scripts/benchmark_exploration.py) | [test_analysis_jobs.py](../tests/test_analysis_jobs.py), [test_rebuild_scatter.py](../tests/test_rebuild_scatter.py), [test_scatter3d.py](../tests/test_scatter3d.py), [test_selection.py](../tests/test_selection.py) |
| Image, annotations and references | [rebuild_annotations_smoke.py](../scripts/rebuild_annotations_smoke.py), [rebuild_image_profiles_smoke.py](../scripts/rebuild_image_profiles_smoke.py), [rebuild_image_comparisons_smoke.py](../scripts/rebuild_image_comparisons_smoke.py), [rebuild_table_smoke.py](../scripts/rebuild_table_smoke.py), [rebuild_records_smoke.py](../scripts/rebuild_records_smoke.py), [box_overlay_resources.py](../scripts/box_overlay_resources.py), [benchmark_references.py](../scripts/benchmark_references.py) | [test_rebuild_annotations.py](../tests/test_rebuild_annotations.py), [test_rebuild_images.py](../tests/test_rebuild_images.py), [test_references.py](../tests/test_references.py) |
| Structured, array and checkpoint sources | [rebuild_sources_smoke.py](../scripts/rebuild_sources_smoke.py), [rebuild_numeric_smoke.py](../scripts/rebuild_numeric_smoke.py), [rebuild_gallery_smoke.py](../scripts/rebuild_gallery_smoke.py), [benchmark_objects.py](../scripts/benchmark_objects.py), [benchmark_arrays.py](../scripts/benchmark_arrays.py), [benchmark_checkpoints.py](../scripts/benchmark_checkpoints.py) | [test_rebuild_sources.py](../tests/test_rebuild_sources.py), [test_npz_aligned_records.py](../tests/test_npz_aligned_records.py), [test_array_record_sessions.py](../tests/test_array_record_sessions.py) |
| Audio inspection and comparison | [rebuild_audio_smoke.py](../scripts/rebuild_audio_smoke.py), [rebuild_audio_comparisons_smoke.py](../scripts/rebuild_audio_comparisons_smoke.py), [rebuild_records_smoke.py](../scripts/rebuild_records_smoke.py), [rebuild_media_matrix.py](../scripts/rebuild_media_matrix.py), [benchmark_audio_views.py](../scripts/benchmark_audio_views.py), [benchmark_audio_playback.py](../scripts/benchmark_audio_playback.py) | [test_rebuild_audio.py](../tests/test_rebuild_audio.py), [test_audio_playback.py](../tests/test_audio_playback.py) |
| Profiles, relationships and interpretations | [rebuild_categories_smoke.py](../scripts/rebuild_categories_smoke.py), [rebuild_pairs_smoke.py](../scripts/rebuild_pairs_smoke.py), [rebuild_axes_smoke.py](../scripts/rebuild_axes_smoke.py), [rebuild_gui_smoke.py](../scripts/rebuild_gui_smoke.py), [rebuild_media_matrix.py](../scripts/rebuild_media_matrix.py) | [test_rebuild_plot_controls.py](../tests/test_rebuild_plot_controls.py), [test_rebuild_relationships.py](../tests/test_rebuild_relationships.py), [test_column_roles.py](../tests/test_column_roles.py), [test_nested_columns.py](../tests/test_nested_columns.py) |
| Comparisons | [rebuild_comparisons_smoke.py](../scripts/rebuild_comparisons_smoke.py), [rebuild_text_comparisons_smoke.py](../scripts/rebuild_text_comparisons_smoke.py), [rebuild_image_comparisons_smoke.py](../scripts/rebuild_image_comparisons_smoke.py), [rebuild_audio_comparisons_smoke.py](../scripts/rebuild_audio_comparisons_smoke.py), [benchmark_comparisons.py](../scripts/benchmark_comparisons.py) | [test_rebuild_comparisons.py](../tests/test_rebuild_comparisons.py) |
| Loading, recovery, sessions, shell and persistence | [rebuild_browser_smoke.py](../scripts/rebuild_browser_smoke.py), [rebuild_imports_smoke.py](../scripts/rebuild_imports_smoke.py), [rebuild_tabs_smoke.py](../scripts/rebuild_tabs_smoke.py), [rebuild_pending_views_smoke.py](../scripts/rebuild_pending_views_smoke.py), [rebuild_workspace_smoke.py](../scripts/rebuild_workspace_smoke.py), [rebuild_layout_restore_smoke.py](../scripts/rebuild_layout_restore_smoke.py) | [test_editor_sessions.py](../tests/test_editor_sessions.py), [test_rebuild_controllers.py](../tests/test_rebuild_controllers.py), [test_multimodal_sessions.py](../tests/test_multimodal_sessions.py) |
| Operations and export | [rebuild_workflow_smoke.py](../scripts/rebuild_workflow_smoke.py), [rebuild_imports_smoke.py](../scripts/rebuild_imports_smoke.py), [benchmark_operations.py](../scripts/benchmark_operations.py), [benchmark_exploration.py](../scripts/benchmark_exploration.py) | [test_editing.py](../tests/test_editing.py), [test_exporting.py](../tests/test_exporting.py), [test_transforms.py](../tests/test_transforms.py) |
| Table and gallery inspection | [rebuild_table_smoke.py](../scripts/rebuild_table_smoke.py), [rebuild_records_smoke.py](../scripts/rebuild_records_smoke.py), [benchmark_references.py](../scripts/benchmark_references.py), [benchmark_inspection.py](../scripts/benchmark_inspection.py) | [test_records.py](../tests/test_records.py), [test_table_presentation.py](../tests/test_table_presentation.py) |
| Text inspection, profiles, training and comparison | [rebuild_text_profiles_smoke.py](../scripts/rebuild_text_profiles_smoke.py), [rebuild_text_comparisons_smoke.py](../scripts/rebuild_text_comparisons_smoke.py), [rebuild_records_smoke.py](../scripts/rebuild_records_smoke.py), [rebuild_table_smoke.py](../scripts/rebuild_table_smoke.py), [benchmark_text_profiles.py](../scripts/benchmark_text_profiles.py), [benchmark_text_inspection.py](../scripts/benchmark_text_inspection.py) | [test_rebuild_text_profiles.py](../tests/test_rebuild_text_profiles.py), [test_text_tokenization.py](../tests/test_text_tokenization.py), [test_rebuild_text_comparisons.py](../tests/test_rebuild_text_comparisons.py) |
| Sizing and docking | [rebuild_gui_smoke.py](../scripts/rebuild_gui_smoke.py), [rebuild_media_matrix.py](../scripts/rebuild_media_matrix.py), [rebuild_docking_smoke.py](../scripts/rebuild_docking_smoke.py), [rebuild_splitter_smoke.py](../scripts/rebuild_splitter_smoke.py) | [test_column_selection_policies.py](../tests/test_column_selection_policies.py), [test_rebuild_controllers.py](../tests/test_rebuild_controllers.py) |
| Unicode fonts | [rebuild_fonts_smoke.py](../scripts/rebuild_fonts_smoke.py) | Direct native glyph presence, baking and visible emoji bounds |

The audio gate uses deterministic injected output to verify native commands and
lifecycle. Actual human listening remains deferred by the user; retiring the old
listening harness does not close that assumption. Titanic human usability gates,
accelerated rendering and other platforms retain their previous status.

Run the current native inventory serially (a Linux display is required):

```bash
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run scripts/rebuild_acceptance.py --matrix
```

Use `--resume` to continue an interrupted run with the same output directory;
the runner validates its saved command list before skipping successful cases.
The runner records each command, exit status, duration and complete log under
`/tmp/datelier-native-acceptance`. `--matrix` adds both shell and media checks for
all nine size/theme combinations. Resource benchmarks retain separate commands
and declared budgets; [gui-overhaul.md](gui-overhaul.md) records their evidence.
