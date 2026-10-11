"""Installed-wheel text/training/statistics and asset integrity outside checkout."""

import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

import polars as pl
import tokenizers

import datelier
from datelier.gui.app import run_gui
from datelier.gui.fonts import FALLBACK_FONTS
from datelier.inspection.references import ReferenceSettings
from datelier.inspection.text.comparisons import (
    TextComparisonSettings,
    TextComparisonSource,
)
from datelier.inspection.text.comparisons.prepare import prepare_comparison
from datelier.inspection.text.comparisons.types import TextComparisonInput
from datelier.inspection.text.profiles import calculate_profile
from datelier.inspection.text.profiles.corpus import TextProgress
from datelier.inspection.text.tokenizers import import_tokenizer
from datelier.inspection.text.tokenizers.prepare import prepare_document
from datelier.inspection.text.tokenizers.training import train_tokenizer
from datelier.inspection.text.types import (
    CorpusMode,
    Normalization,
    TextScope,
    TextSettings,
    TextSource,
    TokenMode,
    TokenSettings,
)
from datelier.io.importing import load_file
from datelier.workspace.recipes.codec import decode_record, encode


def main() -> None:
    module = Path(datelier.__file__).resolve()
    assert "site-packages" in module.parts and "torch" not in sys.modules
    emoji = FALLBACK_FONTS[-1]
    assert emoji.is_file() and emoji.with_name("OFL-NotoEmoji.txt").is_file()
    font_digest = hashlib.sha256(emoji.read_bytes()).hexdigest()
    assert (
        font_digest
        == "de6c18832938afc99caf132b39d6a30a19bac7f2e812e28db2535b4608d27551"
    )
    trained = []
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "text.csv"
        pl.DataFrame(
            {"id": range(4), "text": ["A e\u0301 中🙂", None, "beta beta", ""]}
        ).write_csv(source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        dataset = load_file(source).dataset
        settings = TextSettings(
            "text",
            TextSource.INLINE,
            tokens=TokenSettings(normalization=Normalization.NFC),
            scope=TextScope(CorpusMode.COLLECTION),
        )
        profile = calculate_profile(
            dataset,
            "first",
            settings,
            (),
            ReferenceSettings(),
            None,
            Event(),
            TextProgress(),
        )
        assert (profile.tokens, profile.documents, profile.nulls, profile.empty) == (
            6,
            3,
            1,
            1,
        )
        for mode in (TokenMode.BPE, TokenMode.UNIGRAM):
            recipe = replace(
                settings,
                scope=TextScope(CorpusMode.SELECTION),
                training=replace(
                    settings.training,
                    mode=mode,
                    vocabulary_size=64,
                    min_frequency=1,
                    output_path=str(root / f"{mode}.json"),
                ),
            )
            artifact = train_tokenizer(
                dataset,
                "first",
                recipe,
                (0, 2),
                ReferenceSettings(),
                None,
                Event(),
                TextProgress(),
            )
            assert artifact.documents == 2 and artifact.requested == 2
            reference = import_tokenizer(Path(artifact.reference.path))
            loaded = replace(
                recipe, tokens=replace(recipe.tokens, mode=mode, artifact=reference)
            )
            assert decode_record(TextSettings, encode(loaded)) == loaded
            document = prepare_document(
                dataset, "first", loaded, ReferenceSettings(), None
            )
            assert document.tokens and document.document.text == "A e\u0301 中🙂"
            trained.append(mode.value)
        mappings = tuple(
            TextComparisonSource(name, "text", TextSource.INLINE, scope=settings.scope)
            for name in ("first", "second")
        )
        result = prepare_comparison(
            tuple(TextComparisonInput(m, dataset, m.file_id) for m in mappings),
            TextComparisonSettings(mappings, settings.tokens),
            Event(),
            TextProgress(),
        )
        assert [p.tokens for p in result.profiles] == [6, 6]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert "torch" not in sys.modules
    assert callable(run_gui)
    print(
        json.dumps(
            {
                "python": sys.version.split()[0],
                "module": str(module),
                "tokenizers": tokenizers.__version__,
                "trained": trained,
                "profile_tokens": 6,
                "comparison_tokens": [6, 6],
                "packaged_font_sha256": font_digest,
                "source_preserved": True,
                "torch_imported": False,
                "torch_available": importlib.util.find_spec("torch") is not None,
            }
        )
    )


if __name__ == "__main__":
    main()
