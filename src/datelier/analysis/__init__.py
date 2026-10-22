"""Explicit, revision-bound clustering and coordinate reduction.

``algorithms.ALGORITHMS`` is the trusted catalog of immutable executable method
objects. Each owns its fields, GUI schema, input constraints, sample limits,
estimator construction, and fit facade; legacy parameter names alias those same
classes. Catalog imports do not load estimators or GUI libraries.

Only an explicit Run command starts fitting in a spawned worker. Input
preparation carries source-row IDs through finite-value exclusion, optional
median imputation, constant removal, seeded sampling, and scaling. Results retain
those IDs plus settings, exclusions, warnings, runtime, and library provenance.
Loading, selecting, and restoring never fit models; fitted results are not saved.
"""
