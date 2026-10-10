"""Single-record worker preparation, separate from job ownership/publication."""

from datelier.core.dataset import Dataset
from datelier.inspection.references.index import ReferenceIndex
from datelier.inspection.references.types import ReferenceSettings
from datelier.inspection.text.records import read_document
from datelier.inspection.text.tokenization import TextTokenizer
from datelier.inspection.text.types import TextSettings, TokenizedDocument


def prepare_document(
    dataset: Dataset,
    file_id: str,
    settings: TextSettings,
    references: ReferenceSettings,
    index: ReferenceIndex | None,
) -> TokenizedDocument:
    settings.validate()
    if settings.column is None:
        raise ValueError("Choose a text field")
    document = read_document(
        dataset,
        file_id,
        settings.column,
        settings.position,
        source=settings.source,
        encoding=settings.encoding,
        references=references,
        index=index,
        element_index=settings.element_index,
    )
    return TextTokenizer(settings.tokens).encode(document)
