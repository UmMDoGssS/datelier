"""Deterministic fixtures and instrumentation shared by development checks.

Synthetic tables and multimodal sources stay outside the application wheel.
Native input/motion and injected audio devices support reproducible automated
checks without claiming human usability, audible output, or extra platform
support. Fixtures preserve stable row identities and explicit sampling scopes.
"""
