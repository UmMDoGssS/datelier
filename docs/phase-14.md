# Phase 14 — Audio inspection and integrated acceptance

Phase 14 remains open. Scope and exit gates are in
[ROADMAP.md](../ROADMAP.md#phase-14--audio-inspection-and-integrated-acceptance).
Phase 13 passes; the worktree was clean at entry (`97a86bd`).

## Delivery steps

1. Establish Python 3.14/Linux SoundFile, SoundDevice and SciPy feasibility,
   codec decoding and Linux runtime requirements.
2. Add worker-owned header-first file/mapped-array audio reads, configurable
   array sample rates, bounded signal blocks and explicit signal profiles.
3. Prepare and render waveform envelopes, spectrograms and mel views with
   original-rate provenance, navigable ranges and persisted controls.
4. Add an independent bounded playback lifecycle, explicit listening controls,
   file-owned statistics and cross-file comparisons; verify no autoplay.
5. Harden mixed-source closure/restoration and run full correctness, native
   modality, resource and clean base/checkpoint installation acceptance.

Each coherent step is checked, reviewed and committed before the next. Every
milestone exit requires its full suite and acceptance gates. Actual hardware
playback has a separate gate from decoder/library feasibility. Existing Titanic
usability gates retain their status.

## Acceptance budgets

Establish these fixture-specific targets before measurements. Metadata for a
10-minute stereo 48 kHz WAV should prepare within **0.5 s**; a visible range's
waveform envelope within **2 s**. An explicit exact statistics scan of that file
should finish within **10 s**, with fresh-process peak RSS increase under
**64 MiB** beyond imports/fixture generation. Signal decoding uses bounded
blocks, default **65,536 frames**; retained display preparation defaults to
**16 MiB**, with separately recorded array temporary storage. Long-file access
must remain possible under the budget. GUI frame p95 remains **33 ms**.

Spectral acceptance will record FFT/hop/range dimensions, preparation time,
retained CPU/GPU bytes and any aggregation before its gate is judged. Playback
acceptance will record output device/rate, bounded buffered frames, range/seek/
pause/volume/stop observations and cleanup. Mixed-session and comparison budgets
will be set before those measurements.

## Evidence

### Dependency foundation (2026-10-08)

SoundFile and SoundDevice were added with `uv add`; SciPy was already locked.
[SoundFile's official documentation](https://python-soundfile.readthedocs.io/en/latest/index.html)
describes block decoding and bundled Linux libsndfile wheels.
[SoundDevice's installation documentation](https://github.com/spatialaudio/python-sounddevice/blob/master/doc/installation.rst)
requires Linux PortAudio separately. The reference machine lacks a system
PortAudio installation; a downloaded Ubuntu `libportaudio2` runtime is extracted
under `/tmp/datelier-audio-system` for feasibility tests. This temporary runtime
is not a shipped application dependency or a clean-install result.

`scripts/audio_dependency_probe.py` passes on Python **3.14.7**, SoundFile
**0.14.0** / libsndfile **1.2.2**, SoundDevice **0.5.6**, SciPy **1.18.1** and
PortAudio **19.7.0-devel**. Four one-second stereo 24 kHz/440 Hz fixtures
(WAV/FLAC/OGG and independently FFmpeg-encoded MP3) retain **24,000 frames**,
correct headers and expected decoded RMS within the stated lossy tolerance.
Headers take under **0.5 ms**; 4,096-frame decoding blocks retain at most
**65,536 bytes**, with unchanged source hashes. The probe enumerates 15 host
devices including the PipeWire analog output. Playback is explicitly unverified.
See [dependency evidence](evidence/phase14/audio-dependencies.json).

The probe runs with
`LD_LIBRARY_PATH=/tmp/datelier-audio-system/runtime/usr/lib/x86_64-linux-gnu`
and `uv --cache-dir /tmp/datelier-uv-cache run python scripts/audio_dependency_probe.py --output docs/evidence/phase14/audio-dependencies.json`.
Host audio enumeration requires execution outside the restricted sandbox.
The cache override keeps uv writes in an allowed directory.

Focused existing media/mapping tests: **17 passed**. Pyrefly: **zero errors**,
one existing suppression; Ruff lint/format (**519 files**), offline lock check
(**50 packages**) and diff whitespace pass. No GUI behavior changed in this
dependency step. A default-quality libsndfile-generated anti-phase MP3 fixture
changed RMS markedly; final MP3 feasibility uses an independent FFmpeg encoder.
Inspection must preserve decoded input values rather than assume a lossy
encoding matches its uncompressed generator. M14.1–M14.4 remain open.

### Header and block-loading foundation (2026-10-08)

Audio locators retain file/view/revision/column/source-row identity. File
headers are read before samples; mapped array headers retain original dtype,
sample/channel axes and stable source indices after sorting. Missing array rates
remain unknown, and time-based consumers must request explicit configuration.
File rates are always original; a configured array rate cannot change them.
Raw array values, including integer byte order and nonfinite floats, are preserved.
Files expose libsndfile's decoded float64 full-scale amplitudes with original
format/subtype/rate provenance. Unsupported/corrupt/missing sources have diagnostics.

Worker-only readers stream bounded blocks (at most 65,536 frames/**1 MiB**),
hold one file handle/array lease per command and return read-only owned windows.
Windows exceeding CPU retention ask for a smaller range; streaming consumers can
still inspect the complete signal. Superseding a file/view/revision or closing
during metadata/sample work retires publication and cooperatively releases
decoder handles and oversized temporary-array leases. No playback backend is
imported by this subsystem.

Focused audio/storage/record/media tests: **44 passed**. They cover varied rates,
mono/stereo/four-channel values, source preservation, three mapped axis orders,
compressed/uncompressed and big-endian arrays, null/corrupt/missing sources,
explicit duplicate-stem mappings, nonfinite/empty ranges, budget diagnostics,
cancellation and closure during executing work. Pyrefly reports **zero errors**,
one existing suppression; Ruff lint/format (**527 files**) and diff whitespace pass.
No native controls changed in this foundation slice; signal statistics/native
Inspect integration and milestone/full-suite acceptance remain open.

`scripts/benchmark_audio_loading.py` passes in a fresh process. A **10-minute
stereo 48 kHz PCM16 WAV** (28,800,000 frames) prepares metadata in **2.76 ms**
and an exact final-second window in **0.74 ms**. Complete block iteration retains
at most **1,048,576 bytes** per block with no file temporary storage. A compressed
**20×48,000×2 float32** mapped array reads headers without extraction, then
extracts its selected member once (**7,680,128 temporary bytes**) for a final
500-frame window in **2.81 ms**. Oversized member retention returns to zero and
close removes its temporary directory. Peak RSS increase, including fixture
creation, is **28.64 MiB**, within the established 64 MiB target. Source hashes
remain unchanged. See [loading resource evidence](evidence/phase14/audio-loading-resources.json).
