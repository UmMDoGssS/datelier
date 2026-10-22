"""Typed per-format drafts and transactional background reimport commands.

Automatic opening detects source format; explicit options select strict adapters.
Reimport resets history only after success, retaining the prior dataset on
failure. Abandonment invalidates publication while an executing parser may finish.
Draft settings remain independent for each file and format.
"""

from datelier.application.imports.controller import ImportController as ImportController
from datelier.application.imports.drafts import DEFAULTS as DEFAULTS
from datelier.application.imports.drafts import import_draft as import_draft
