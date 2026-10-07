"""Explicit corpus scope and local training controls."""

from dataclasses import replace

from imgui_bundle import imgui

from datelier.inspection.text.jobs import TextJobs
from datelier.inspection.text.types import CorpusMode, TextScope, TokenMode


def scope_controls(scope: TextScope) -> TextScope:
    modes = list(CorpusMode)
    _, mode = imgui.combo(
        "Corpus records", modes.index(scope.mode), [m.value for m in modes]
    )
    start, count, seed = scope.start, scope.count, scope.seed
    if modes[mode] in (CorpusMode.RANGE, CorpusMode.RANDOM):
        if modes[mode] == CorpusMode.RANGE:
            _, start = imgui.input_int("Corpus first row", start)
        _, count = imgui.input_int("Corpus record count", count)
        if modes[mode] == CorpusMode.RANDOM:
            _, seed = imgui.input_int("Corpus sample seed", seed)
    imgui.text_wrapped(
        "Current table rows only. Linked selection and seeded sampling retain "
        "source IDs. Entire-collection work begins only on command."
    )
    return TextScope(
        modes[mode], max(1, start), max(1, count), max(0, min(seed, 2**32 - 1))
    )


def training_controls(jobs: TextJobs) -> bool:
    settings = jobs.settings
    training = settings.training
    scope = scope_controls(settings.scope)
    modes = [TokenMode.BPE, TokenMode.UNIGRAM]
    _, mode = imgui.combo(
        "Training model", modes.index(training.mode), [m.value for m in modes]
    )
    _, vocabulary = imgui.input_int("Vocabulary size", training.vocabulary_size)
    frequency, length, iterations, shrink = (
        training.min_frequency,
        training.max_piece_length,
        training.iterations,
        training.shrinking_factor,
    )
    if modes[mode] == TokenMode.BPE:
        _, frequency = imgui.input_int("Minimum token frequency", frequency)
    else:
        _, length = imgui.input_int("Maximum piece length", length)
        _, iterations = imgui.input_int("Unigram iterations per pruning", iterations)
        _, shrink = imgui.input_double("Unigram shrinking factor", shrink)
    _, special = imgui.input_text(
        "Special tokens (comma-separated)", ",".join(training.special_tokens)
    )
    _, output = imgui.input_text("New tokenizer JSON path", training.output_path)
    imgui.text_wrapped(
        "Training uses the text field, encoding, normalization and lowercase "
        "controls above. Unicode word/punctuation pre-tokenization; [UNK] is "
        "required first. Local files include a provenance sidecar. The trainer "
        "has no configurable random seed; reuse the saved artifact for "
        "reproducible encoding."
    )
    jobs.settings = replace(
        settings,
        scope=scope,
        training=replace(
            training,
            mode=modes[mode],
            vocabulary_size=vocabulary,
            min_frequency=frequency,
            max_piece_length=length,
            iterations=iterations,
            shrinking_factor=shrink,
            special_tokens=tuple(s.strip() for s in special.split(",")),
            output_path=output,
        ),
    )
    return imgui.button("Train local tokenizer")
