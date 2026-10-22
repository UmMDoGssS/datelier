"""Local text tokenization, exact corpus profiles, and original-span inspection.

Character, whitespace, and Unicode word modes expose normalization and special
token settings; BPE/Unigram use explicitly loaded or locally trained artifacts.
Token offsets count original Unicode code points even after normalization.
Scalar records and streamed List[Text] leaves retain row/element provenance.
Full text, token lists, and exact frequency tables remain available through
paging; only plotted views are bounded. Collection work and training are explicit.
"""

from datelier.inspection.text.lists import is_text_field as is_text_field
from datelier.inspection.text.lists import is_text_list as is_text_list
