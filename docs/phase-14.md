# Phase 14 — Audio inspection and integrated acceptance

Phase 14 remains open. Scope and exit gates are in
[ROADMAP.md](../ROADMAP.md#phase-14--audio-inspection-and-integrated-acceptance).
Phase 13 passes; the worktree was clean at entry (`97a86bd`). M14.1 passes;
M14.2–M14.4 remain open.

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

### Exact signal statistics foundation (2026-10-08)

Explicit commands scan the selected record/range for per-channel original
minimum/maximum/peak, finite/nonfinite counts, mean and stable RMS, clipping and
silence counts. Default clipping uses original PCM/dtype rails (including the
asymmetric positive PCM16 rail); custom clipping amplitudes are symmetric and
explicit. Silence uses an absolute threshold in original signal units. Aggregate
silence requires every channel to be finite and silent; longest runs remain exact
across decoding blocks. Nonfinite values are excluded from finite denominators
and never count as silent or clipped. Thresholds and range accompany the result.
Original integer extrema remain exact, including UInt64. Scaled long-double RMS
avoids overflow from finite 1e300 samples. Summaries outside Float64 reporting
range receive a diagnostic while original extrema remain available.

Metadata and sample-window preparation do not launch a statistics scan. Profile
jobs have separate cooperative cancellation/progress; switching record/rate/
file/view/revision or closing retires their publication. File handles and array
leases remain worker-owned. Native controls and persistence are still pending.

Focused audio/statistics/storage/record/media tests: **57 passed**. Pyrefly:
**zero errors**, one existing suppression; Ruff lint/format (**530 files**) and
diff whitespace pass. No GUI behavior changed in this backend slice.
The extended loading benchmark scans all **28,800,000 stereo frames** in
**2.31 s**, producing exact mean/RMS **0.25** per channel, zero silence/clipping,
and original **600 s** duration. Peak RSS increase including fixtures is
**31.03 MiB**; file temporary storage remains zero. Compressed-array extraction
and cleanup/source-hash gates continue to pass.
See [signal resource evidence](evidence/phase14/audio-signal-resources.json).
M14.1 remains open for native controls, saved configuration and full acceptance;
M14.2–M14.4 also remain open.

### Native Inspect and M14.1 acceptance (2026-10-08)

Focused Inspect routes audio roles, recognized audio references in mixed media,
and confirmed waveform mappings to header-first audio tools beside arbitrary
supporting fields. Homogeneous audio folders retain explicit audio roles.
Users configure unknown array rates, original-frame ranges/channels, original
clipping rails or custom amplitudes, silence thresholds and explicit complete/
selected-range profiles. An explicit sample command shows original dtype values
in a virtual table with frame/time positions. Settings round-trip in legacy and
whole-session workspaces; decoded samples and statistics are never bundled.
Restored file views read only visible headers. Mapped views use the existing
explicit Prepare saved array records command for supporting arrays/history,
then restore metadata without waveform samples/statistics. The playback backend
is not imported during these native workflows.

`scripts/audio_inspect_smoke.py` drives real mouse/key/scroll input on Linux/Mesa
software OpenGL. File controls pass **282 frames**, p95 **10.65 ms**; an idle
fresh-process restoration passes **28 frames**, p95 **10.81 ms**. Mapped arrays
pass **332 frames**, p95 **11.70 ms**, including native **8 kHz** configuration,
sorting to original row **1**, preserved supporting label **1**, second-channel
samples **−0.5**, exact RMS **0.5** and explicit **8,000** clipped samples under
the custom **±0.2** threshold. A native saved-record preparation and idle restore
passes **46 frames**, p95 **11.70 ms**. Both retain the chosen 1,024-frame window,
channel and thresholds, preserve source hashes, and keep exact sample rendering
below 100 visible rows. The first native run exposed a zero-height statistics
table; an explicit bounded table height fixes it. Final screenshots are visually
reviewed with channel statistics and exact values visible.
See [file evidence](evidence/phase14/audio-file-native.json) and
[mapped-array evidence](evidence/phase14/audio-array-native.json).

Focused audio/workspace/media/state checks pass **58 tests**. Full M14.1 suite:
**932 passed in 22.60 s**, with three existing restricted-checkpoint warnings.
`uv run pyrefly check`: **zero errors**, one existing suppression;
`uv run ruff check .` and `uv run ruff format --check .` pass (**536 files**).
Offline lock validation (**50 packages**), diff whitespace and local document
links are checked before commit. The Inspect renderer remains cohesive at
337 lines; audio computation, controls and statistics rendering have separate
owners. The 309-line native driver is one complete save/restore workflow.

M14.1 now passes dependency/codec feasibility, known original signal metadata/
statistics, missing-rate/malformed diagnostics, bounded reads, cancellation,
source preservation, saved controls, native file/array restoration and measured
resource gates. Actual playback, waveform/spectral/mel views, collection
comparisons, integrated multimodal and clean-install acceptance remain in the
following open milestones.

### M14.2 preparation and resource targets (2026-10-08)

The next step prepares exact waveform-bin extrema and one-sided power-density
spectra from original-rate bounded blocks. Periodic Hann/Hamming/rectangular
windows have explicit FFT/hop settings and no implicit detrending. Short records
use their actual window length and zero-pad only the FFT; complete long-record
windows may leave at most hop−1 trailing samples, labelled with access through a
selected tail range. Nonfinite samples become zero solely in spectral views,
with a count. Frequency/time display aggregation retains peak PSD and is labelled;
exact cells remain available by narrowing time/frequency ranges or raising display
bin limits. Waveform extrema retain source dtypes separately from Float64 plotting.

Before judging this step, retain the established **2 s** full 10-minute stereo
48 kHz waveform-envelope target and **33 ms** frame p95. A selected **60 s**
48 kHz spectrum with FFT **1,024**, hop **256** and default display bins should
prepare within **10 s**, retain at most **16 MiB**, and have a fresh-process peak
RSS increase under **96 MiB**, including bounded fixture creation. Record array
extraction count, temporary disk, post-command retention, source hashes and close
cleanup. Mel and native-view gates remain open until their later slices.

### Waveform/spectral preparation foundation (2026-10-08)

The worker foundation above passes **59 focused tests** covering original
extrema/time centers, sparse impulses, three windows, hop sizes 1/173/512,
decoder-block boundaries, independent [SciPy PSD references](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.signal.stft.html),
one-sided normalization, short-window FFT padding, frequency cropping,
nonfinite-to-zero provenance, decibel floors, display aggregation and source
preservation. UInt64 extrema remain exact independently of Float64 plotting.
Channel-specific array reads avoid copying unselected channels, including a
262,145-channel fixture inspected under a 1 KiB envelope budget. Compressed
members hold one lease for each spectral command, extract once, and release
oversized storage afterward. Raw all-channel sample reads retain their contracts.

Visible-view jobs are independent of metadata, original sample windows and exact
profiles. Irrelevant FFT settings do not rebuild waveforms; linear-power views
ignore decibel-floor changes. Changing only display scale reuses immutable PSD
through a worker conversion. Source/file/view/revision/rate/channel/range changes
retire affected publication, and closure during a executing source read releases
the reader without publishing obsolete work. GUI integration remains pending.

`scripts/benchmark_audio_views.py` passes established targets: the complete
**10-minute stereo 48 kHz** waveform prepares in **0.169 s**, retains **131,072
bytes**, and preserves ±0.25 extrema. The final **60 s** spectrum prepares in
**0.199 s**, retaining **15,409,104 bytes** for a **513×1,875** grid over **11,247**
original FFT windows. Six-window time peak aggregation is explicit; frequencies
remain unaggregated and the known tone peaks at **1,500 Hz**. A compressed
**10×48,000×2 float32** member prepares in **6.15 ms**, extracts once
(**3,840,128 temporary bytes**), and returns to zero retained disk bytes.
Peak RSS increase, including fixture creation, is **36.23 MiB**; file temporary
storage is zero, hashes are unchanged, and close removes array temporary paths.
See [view resource evidence](evidence/phase14/audio-view-resources.json).

Pyrefly reports **zero errors**, one existing suppression; Ruff lint/format
(**544 files**) and diff whitespace pass. No GUI behavior changed in this
foundation step. M14.2 remains open for native controls, mel views, saved
recipes and milestone/full-suite acceptance. M14.3–M14.4 remain open.
