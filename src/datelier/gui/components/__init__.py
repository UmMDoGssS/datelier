"""Reusable native fields, selectors, tables, plots, and direct-child containers.

Shared components receive narrow bindings or commands, never whole sessions.
Drawing/formatting helpers can remain functions. Preparation stays in domain or
application workers; components render bounded prepared values and expose scoped
probes for native verification.
"""
