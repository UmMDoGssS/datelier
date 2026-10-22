"""CSV/TSV, JSON/JSONL, Parquet, and tabular XML import adapters.

CSV/TSV expose delimiter, quoting, null, inference, and date settings. JSON record
objects preserve compatible nested structs/lists and union missing fields as
null; duplicate keys and nonstandard nonfinite literals fail. Text mode handles
incompatible scalar types. Parquet retains supported stored types. XML accepts
explicit scalar-record paths and namespaces, rejecting unsupported nesting or
mixed content rather than dropping it. Batched parsers still produce a complete
in-memory table; they are not an out-of-core table engine.
"""

from datelier.io.tabular.csv import CsvImport as CsvImport
from datelier.io.tabular.csv import CsvOptions as CsvOptions
from datelier.io.tabular.csv import load_csv as load_csv
from datelier.io.tabular.csv import load_tsv as load_tsv
from datelier.io.tabular.json import decode_json as decode_json
from datelier.io.tabular.json import load_json as load_json
from datelier.io.tabular.parquet import load_parquet as load_parquet
from datelier.io.tabular.records import RecordValue as RecordValue
from datelier.io.tabular.records import records_to_table as records_to_table
from datelier.io.tabular.xml import load_xml as load_xml
