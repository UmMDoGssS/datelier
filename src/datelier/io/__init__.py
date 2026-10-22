"""Read-only import adapters and explicit export, intended for background workers.

Tabular adapters produce in-memory Polars datasets. Structured objects, arrays,
checkpoints, and media open hierarchy/header metadata before selected payloads.
``load_inspectable_file`` adds automatic structured-JSON fallback for editor
opening; explicit format/options retain strict import diagnostics. Export writes
user columns to a separate CSV/Parquet destination and protects source aliases.
"""
