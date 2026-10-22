"""Versioned referenced-source recipes, whole sessions, and user preferences.

Sessions retain tab order/active tab, independent import/history/view recipes,
selections, comparison mappings, and layout. Source/media/tokenizer references
remain external: no source snapshots, decoded caches, or fitted ML results are
bundled. Workers validate fingerprints and replay operations; missing/changed
sources recover independently while usable tabs remain available. Saving and
explicit export protect source files and aliases.
"""
