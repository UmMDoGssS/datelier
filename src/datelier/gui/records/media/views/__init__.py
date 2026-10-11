"""Media record views consume the shared pixel/texture primitives."""

from datelier.gui.records.media.views.audio import AudioContent as AudioContent
from datelier.gui.records.media.views.audio import (
    AudioMetadataView as AudioMetadataView,
)
from datelier.gui.records.media.views.audio import SignalProvenance as SignalProvenance
from datelier.gui.records.media.views.images import ImageContent as ImageContent
from datelier.gui.records.media.views.text import OriginalText as OriginalText
from datelier.gui.records.media.views.text import TextContent as TextContent
from datelier.gui.records.media.views.text import TokenPiece as TokenPiece
from datelier.gui.records.media.views.text import TokenRows as TokenRows
from datelier.gui.records.media.views.text import Tokens as Tokens
