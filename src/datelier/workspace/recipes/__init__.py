"""Finite typed JSON recipe encoding; saved input never chooses Python imports.

Domain-owned registry groups enumerate allowed dataclasses/enums. Decode validates
field names and shapes before replay. Algorithm recipe identifiers and legacy
parameter aliases must remain compatible; new methods register their executable
class rather than a second parameter type. Old array recipes default to metadata
views so migration preserves their row identity.
"""

from datelier.workspace.recipes.codec import RECORDS as RECORDS
from datelier.workspace.recipes.codec import decode as decode
from datelier.workspace.recipes.codec import decode_record as decode_record
from datelier.workspace.recipes.codec import encode as encode
