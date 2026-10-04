from datetime import date
from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from datelier.import_types import ImportFailure, XmlOptions
from datelier.importing import load_file
from datelier.inspection import prepare_inspection


def xml_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "table[1].xml"
    path.write_text(text)
    return path


def test_xml_values_types_missing_fields_attributes_and_identity(
    tmp_path: Path,
) -> None:
    text = (
        '<rows><row id="9"><value unit="kg">1.5</value><label>café</label>'
        '<flag>true</flag></row><row id="3"><label>last</label>'
        "<flag>false</flag><late>2</late></row></rows>"
    )
    path = xml_file(tmp_path, text)
    imported = load_file(path)
    assert imported.dataset.table.schema == {
        "@id": pl.Int64,
        "value": pl.Float64,
        "value/@unit": pl.String,
        "label": pl.String,
        "flag": pl.Boolean,
        "late": pl.Int64,
    }
    assert imported.dataset.table.rows() == [
        (9, 1.5, "kg", "café", True, None),
        (3, None, None, "last", False, 2),
    ]
    inspection = prepare_inspection(imported)
    assert inspection.first_page.row_ids == (0, 1)
    assert inspection.schema[1].null_count == 1
    assert path.read_text() == text


def test_xml_namespaces_paths_and_deterministic_extraction(tmp_path: Path) -> None:
    path = xml_file(
        tmp_path,
        '<root xmlns="urn:rows" xmlns:a="urn:attrs">'
        "<metadata><title>x</title></metadata><data>"
        '<record a:id="1"><value>2</value></record>'
        '<record a:id="3"><value>4</value></record></data></root>',
    )
    options = XmlOptions(
        record_path="./r:data/r:record", namespaces=(("r", "urn:rows"),)
    )
    first = load_file(path, options)
    second = load_file(
        path, XmlOptions(record_path="./{urn:rows}data/{urn:rows}record")
    )
    assert_frame_equal(first.dataset.table, second.dataset.table)
    assert first.dataset.table.columns == ["@{urn:attrs}id", "{urn:rows}value"]
    assert first.dataset.table.rows() == [(1, 2), (3, 4)]
    assert first.dataset.row_ids.to_list() == second.dataset.row_ids.to_list() == [0, 1]


def test_xml_type_and_text_options(tmp_path: Path) -> None:
    path = xml_file(
        tmp_path,
        '<rows><row id="001"><day>2026-10-04</day><value>NA</value>'
        "<label> padded </label></row><row><day/><value>2</value></row></rows>",
    )
    inferred = load_file(path, XmlOptions(null_values=("NA",), try_parse_dates=True))
    assert inferred.dataset.table.row(0) == (1, date(2026, 10, 4), None, "padded")
    text = load_file(
        path, XmlOptions(infer_types=False, strip_text=False, include_attributes=False)
    )
    assert text.dataset.table.row(0) == ("2026-10-04", "NA", " padded ")
    assert text.dataset.table.dtypes == [pl.String] * 3
    assert "1 attributes explicitly excluded" in text.diagnostics[-1]


@pytest.mark.parametrize(
    "text, message",
    [
        ("<rows><row><x><y>1</y></x></row></rows>", "field.*x.*nested XML"),
        ("<rows><row><x>1</x><x>2</x></row></rows>", "repeated fields"),
        ("<rows><row>before<x>1</x></row></rows>", "mixed or scalar"),
        ("<rows><row><x>1</x>after</row></rows>", "mixed XML text"),
        ("<rows><row/></rows>", "no fields"),
        ("<rows/>", "No XML records"),
        ("<rows>", "Malformed XML"),
        ("", "Malformed XML"),
        (
            '<!DOCTYPE rows [<!ENTITY x "data">]><rows><row><x>&x;</x></row></rows>',
            "DTD/entity",
        ),
        (
            "<rows><row><x>99999999999999999999999999999999</x></row></rows>",
            "read as text",
        ),
        ("<rows><row><x>1e999</x></row></rows>", "finite numeric range"),
    ],
)
def test_xml_rejects_unsupported_shapes_and_bad_types(
    tmp_path: Path, text: str, message: str
) -> None:
    path = xml_file(tmp_path, text)
    with pytest.raises(ImportFailure, match=message):
        load_file(path)
    assert path.read_text() == text


def test_xml_deeper_records_and_root_record_are_explicitly_supported(
    tmp_path: Path,
) -> None:
    path = xml_file(
        tmp_path,
        "<root><group><record><value>1</value></record><record><value>2</value></record></group></root>",
    )
    assert load_file(
        path, XmlOptions(record_path=".//record")
    ).dataset.table.rows() == [(1,), (2,)]
    path = xml_file(tmp_path, "<record><x>3</x></record>")
    assert load_file(path, XmlOptions(record_path=".")).dataset.table.rows() == [(3,)]


@pytest.mark.parametrize("path", ["./missing", ".//p:row", "["])
def test_xml_bad_path_has_actionable_diagnostic(tmp_path: Path, path: str) -> None:
    source = xml_file(tmp_path, "<rows><row><x>1</x></row></rows>")
    with pytest.raises(ImportFailure, match="path|records"):
        load_file(source, XmlOptions(record_path=path))


@pytest.mark.parametrize(
    "options",
    [
        XmlOptions(record_path="."),
        XmlOptions(record_path=".//row"),
    ],
)
def test_xml_namespaces_do_not_collapse_distinct_names(
    tmp_path: Path, options: XmlOptions
) -> None:
    source = xml_file(
        tmp_path,
        '<row xmlns:a="urn:a" xmlns:b="urn:b"><a:x>1</a:x><b:x>2</b:x></row>'
        if options.record_path == "."
        else (
            '<rows><row xmlns:a="urn:a" xmlns:b="urn:b">'
            "<a:x>1</a:x><b:x>2</b:x></row></rows>"
        ),
    )
    assert load_file(source, options).dataset.table.columns == ["{urn:a}x", "{urn:b}x"]


def test_xml_options_validation() -> None:
    with pytest.raises(ValueError, match="nonempty"):
        XmlOptions(record_path=" ")
    with pytest.raises(ValueError, match="unique"):
        XmlOptions(namespaces=(("a", "one"), ("a", "two")))


def test_xml_batches_preserve_order_late_types_and_empty_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import datelier.import_records as batches

    monkeypatch.setattr(batches, "BATCH_RECORDS", 2)
    monkeypatch.setattr(batches, "BLOCK_BATCHES", 2)
    path = xml_file(
        tmp_path,
        "<rows><row/><row/><row><x>1</x></row><row/>"
        "<row><x>2.5</x><late>true</late></row><row/></rows>",
    )
    imported = load_file(path)
    assert imported.dataset.table.schema == {"x": pl.Float64, "late": pl.Boolean}
    assert imported.dataset.table.rows() == [
        (None, None),
        (None, None),
        (1.0, None),
        (None, None),
        (2.5, True),
        (None, None),
    ]
    assert imported.dataset.row_ids.to_list() == list(range(6))


def test_xml_http_namespaces_and_descendant_child_paths(tmp_path: Path) -> None:
    path = xml_file(
        tmp_path,
        '<r:root xmlns:r="https://example.org/data/">'
        "<r:group><r:record><r:x>1</r:x></r:record></r:group>"
        "<r:group><r:record><r:x>2</r:x></r:record></r:group></r:root>",
    )
    uri = "https://example.org/data/"
    first = load_file(
        path, XmlOptions(record_path=f".//{{{uri}}}group/{{{uri}}}record")
    )
    second = load_file(
        path, XmlOptions(record_path=".//r:group/r:*", namespaces=(("r", uri),))
    )
    assert_frame_equal(first.dataset.table, second.dataset.table)
    assert first.dataset.table.rows() == [(1,), (2,)]


def test_xml_non_utf8_declaration_is_explicitly_rejected(tmp_path: Path) -> None:
    path = xml_file(
        tmp_path,
        '<?xml version="1.0" encoding="ISO-8859-1"?><rows><row><x>1</x></row></rows>',
    )
    with pytest.raises(ImportFailure, match="UTF-8 encoding"):
        load_file(path)


def test_xml_encoding_attribute_is_data(tmp_path: Path) -> None:
    path = xml_file(tmp_path, '<rows><row encoding="custom"><x>café</x></row></rows>')
    assert load_file(path).dataset.table.rows() == [("custom", "café")]


def test_xml_declaration_words_in_comments_and_cdata_are_scalar_text(
    tmp_path: Path,
) -> None:
    path = xml_file(
        tmp_path,
        "<rows><!-- <!DOCTYPE example> -->"
        "<?metadata <!ENTITY example> ?>"
        "<row><text><![CDATA[<!DOCTYPE literal> & café]]></text></row>"
        "<row><text>&lt;!ENTITY escaped&gt;</text></row></rows>",
    )
    assert load_file(path).dataset.table.rows() == [
        ("<!DOCTYPE literal> & café",),
        ("<!ENTITY escaped>",),
    ]


def test_xml_declaration_scan_handles_source_chunk_boundaries(tmp_path: Path) -> None:
    # Split both the CDATA opening and closing tokens across decoder chunks.
    chunk = 1024 * 1024
    prefix = "<rows><row><text>"
    padding = " " * (chunk - len(prefix) - 4)
    literal = "<![CDATA[<!DOCTYPE text>"
    rest = "x" * (chunk - len(literal) + 3)
    path = xml_file(
        tmp_path, prefix + padding + literal + rest + "]]></text></row></rows>"
    )
    assert load_file(path).dataset.table.item().startswith("<!DOCTYPE text>")
    path = xml_file(
        tmp_path, " " * (chunk - 4) + "<!DOCTYPE rows><rows><row><x>1</x></row></rows>"
    )
    with pytest.raises(ImportFailure, match="DTD/entity"):
        load_file(path)
