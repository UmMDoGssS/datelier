# Phase 14 — Audio inspection and integrated acceptance

Phase 14 remains open. Scope and exit gates are in
[ROADMAP.md](../ROADMAP.md#phase-14--audio-inspection-and-integrated-acceptance).
Phase 13 passes; the worktree was clean at entry (`97a86bd`). M14.1–M14.2 pass;
M14.3–M14.4 remain open.

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

### Native waveform/spectrogram inspection (2026-10-08)

Inspect now prepares the visible original-rate signal range independently of
exact sample windows and explicit profiles. Time/sample-frame navigation,
channel, FFT/hop/window, frequency limits, scale/floor, display bins, colors,
CPU/GPU retention and plot height are saved. Narrowing the visible time range
requests more detailed source-aligned preparation. Metadata without a known
array rate continues to require configuration. No playback backend is imported.
Color/scale changes reuse immutable PSD through a worker conversion. Workspace
round trips also cover independent file recipes, old defaults and exclusion of
prepared grids, profiles and decoded samples. A codec-reserved field collision
was fixed before registering the new view recipe.

Native mouse/key/scroll controls pass the selected **0.5–1.5 s**, second-channel
waveform extrema **±0.25**, then FFT **512**, hop **128**, Hamming,
**500–3,000 Hz**, **−90 dB** floor and **4/1 MiB** CPU/GPU settings. The
**2,000 Hz** tone has correct hover values and raster frequency orientation,
checked against its prepared color pixel in an asymmetric frequency range.
Save workflow: **688 frames**, p95 **18.91 ms**; fresh-process restore:
**103 frames**, p95 **19.58 ms**, one texture upload, no implicit original-sample
or profile command. See [native evidence](evidence/phase14/audio-spectrum-native.json)
and [restored screenshot](evidence/phase14/audio-spectrum-restored.png).

The first expanded-waveform measurement exceeded the **33 ms** target.
Worker-side removal of redundant drawing points within identical extrema runs
preserves the exact piecewise-linear paths, source bin values, sparse peaks and
nonfinite gaps. The final separate waveform workflow passes **201 frames**,
p95 **19.96 ms**; its [screenshot](evidence/phase14/audio-waveform.png) is visually
checked. No new approximation is introduced by this drawing optimization.
Initial axis padding keeps extrema lines visible at the recording's amplitude
limits.

Full FFT **65,536** resolution retains **32,769 frequency rows** and uses
**17** textures of at most **2,048×2,048** cells. No extra frequency sampling is
needed to fit hardware texture dimensions. Native controls, a visible configured
color range, hover and rendered peak pixel pass **443 frames**, p95 **20.32 ms**,
with **131,076 GPU bytes** retained; see
[large-grid evidence](evidence/phase14/audio-spectrum-large-native.json).
Texture buffers are released while the GL context still exists. CPU budgeting
includes both axes, grids and color tiles, including a tall-frequency fixture
under a **1 MiB** budget. File/sample/profile regression also passes; mapped-array
native controls and fresh-process restoration pass **371/46 frames**, p95
**12.09/11.38 ms**, preserving original row **1** and source hashes; see
[array regression](evidence/phase14/audio-view-array-regression.json).

The final [colored-view resource run](evidence/phase14/audio-view-gpu-resources.json)
passes the predeclared budgets: complete 10-minute waveform **0.146 s**,
**98,352 retained bytes**; final 60-second spectrum **0.233 s**, **16,504,780
retained bytes**, **513×1,607** cells with explicit seven-window peak aggregation.
Peak RSS increase including fixture creation is **64.97 MiB**. Compressed-array
preparation takes **8.57 ms**, extracts once (**3,840,128 temporary bytes**) and
returns to zero retained disk; close removes temporary paths and source hashes
remain unchanged.

**64 focused audio tests** pass. Pyrefly reports **zero errors**, one existing
suppression; Ruff lint/format (**549 files**) and diff whitespace pass.
M14.2 remains open for mel representations, native mel/array controls and
milestone/full-suite acceptance. M14.3–M14.4 remain open.

### Mel preparation targets (2026-10-08)

The next slice uses the HTK mel scale and unit-height triangular filters in Hz,
without area normalization, consistent with the
[documented filter-bank convention](https://docs.pytorch.org/audio/stable/generated/torchaudio.functional.melscale_fbanks.html).
It integrates original one-sided PSD × FFT-bin Hz width into band power in
original amplitude units², before any time display aggregation. Mel-axis hover
reports each band's center in Hz. Empty supports remain zero, counted explicitly.
Sparse supports avoid a dense bands×FFT matrix. FFT/window/hop and original rate
retain the preceding slice's provenance; colors and decibels remain display-only.

Before measurement, require the final **60 s** of the same 10-minute stereo
48 kHz recording, FFT **1,024**, hop **256** and **64 mel bands** to prepare
within **10 s**, retain at most **16 MiB**, and keep fresh-process peak RSS
increase under **96 MiB** including fixture creation. A compressed-array
**512-band**, FFT **65,536** selected-record command must extract once, return to
zero retained oversized disk data and remove temporary paths on close. Native
file/mapped-array controls and fresh restoration retain **33 ms** frame p95.
Mel and M14.2 exit gates remain open until these measurements and checks pass.

### M14.2 mel and milestone acceptance (2026-10-08)

HTK mel views now expose **1–512 bands**, original-frequency limits,
FFT/window/hop and linear band power or display-only decibels. Uniform mel
coordinates retain nonlinear Hz centers for hover. Sparse triangles integrate
each original PSD window before explicit time peak aggregation; no original-rate
resampling or prior frequency display aggregation occurs. Empty filters remain
visible and counted. Waveforms ignore mel settings, ordinary spectra ignore band
counts, and mel views ignore ordinary frequency-display bins. Display color/scale
conversion reuses band power. Source/range/channel/band changes retire affected
work. Saved independent recipes include mel settings; earlier signal recipes
without band counts use defaults. Prepared signals, profiles and playback are
excluded from workspaces.

Analytical Hz edges **0/700/2,100/4,900/10,500** and triangle integrals
**1,050/2,100/4,200** verify the filter convention independently. Dense
SciPy-based references cover rates **8,000/22,050 Hz**, FFT **64/512**,
**1/8/64/512 bands**, frequency cropping, exact original time centers, band-power
units, decibels and peak aggregation. All-empty narrow-band fixtures stay zero
and labelled. A **512-band/65,536-FFT** bank retains sparse support proportional
to FFT bins, below **2 MiB**, rather than allocating a dense matrix.
**71 focused audio tests** pass, including original-source and stale/closed-job
contracts from the preceding slices.

`scripts/audio_mel_smoke.py` drives native file and sorted mapped-array controls:
second channel, **0.5–1.5 s**, FFT **512**, hop **128**, Hamming,
**32 bands**, **500–3,000 Hz**, explicit linear/decibel choices,
**−80 dB** floor and **4/1 MiB** CPU/GPU retention. Known **2,000/2,500 Hz**
tones fall in the expected filter supports; native Hz hover and asymmetric
mel-raster peak colors agree. File workflow/restoration: **626/90 frames**,
p95 **18.34/19.06 ms**. Array workflow/restoration: **658/104 frames**,
p95 **19.07/19.97 ms**, preserving original source row **1**, supporting label
**1**, **8 kHz** configuration and selected record. Each retains **38,488 CPU
bytes** and **7,552 GPU bytes**. Original samples/profiles stay idle, playback is
not imported, and source hashes are unchanged. See
[file evidence](evidence/phase14/audio-mel-file-native.json) and
[array evidence](evidence/phase14/audio-mel-array-native.json); screenshots,
including fresh restoration, are visually checked.

`scripts/audio_long_signal_smoke.py` opens **28,800,000 stereo sample frames**
at **48 kHz**, natively selects the whole recording, then navigates between
**480–540 s** and **540–600 s** mel ranges. The original row/rate/channel,
time coordinates and known **1,500 Hz** tone remain aligned. Native rendering
passes **372 frames**, p95 **18.97 ms**; waveform retention is **98,352 bytes**,
mel retention **2,415,512 CPU / 480,000 GPU bytes**. See
[long-navigation evidence](evidence/phase14/audio-long-signal-native.json).
The shared native input capture/dispatch helper has configured Pyrefly script
resolution and runs through real library return values. The waveform/spectrogram
regression also passes **688/103 frames**, p95 **18.78/19.64 ms** after the helper
change; see [regression evidence](evidence/phase14/audio-spectrum-mel-regression.json).
Performance checks run separately from the full suite: an overlapping heavy test
run exceeded the restore timing budget, while the isolated final run passes.

The [mel resource run](evidence/phase14/audio-mel-resources.json) passes the
predeclared fixture budgets. Final **60 s**, FFT **1,024**, hop **256**, **64 bands**:
**0.239 s**, **2,415,512 retained bytes**, **64×1,875** cells over **11,247**
windows, with six-window time peak aggregation and the known tone's peak band
center **1,513.56 Hz**. Peak RSS increase including fixture creation is
**20.94 MiB**. Compressed **10×48,000×2** data inspected at **512 bands / FFT
65,536** takes **8.01 ms**, extracts once (**3,840,128 temporary bytes**), returns
to zero retained disk and removes temporary paths on close. Source hashes remain
unchanged.

Full M14.2 suite: **967 passed in 24.43 s**, with three existing restricted-
checkpoint warnings. Pyrefly reports **zero errors**, one existing suppression;
Ruff lint/format (**554 files**), offline lock validation (**50 packages**),
document links and diff whitespace pass. M14.2 now passes original extrema,
spectral/mel references, independent invalidation, saved provenance, native
file/array restoration, long navigation, resource and full-suite gates.
M14.3–M14.4 and overall Phase 14 remain open.

### M14.3 bounded playback-buffer foundation (2026-10-08)

Playback preparation now has an explicit original-source/range/channel/seek
recipe and a preallocated output ring, independently testable without a device
or GUI. All channels are preserved unless one is explicitly selected. The ring
tracks contiguous original frame positions, handles wrap/backpressure and final
zero padding without counting padding as source data, and returns silence
without waiting when its producer is busy. Pause preserves its source cursor;
stop discards output. Float64 buffering applies current gain before clipping
and Float32 device conversion. Finite values above full scale therefore retain
their gain behavior. Nonfinite samples become zero solely for playback; original
arrays remain unchanged. Integer arrays use explicit signed rails or unsigned
midpoint PCM mapping, independently of their physical-unit statistics.

**11 focused buffer/conversion tests** pass, including signed/unsigned 16–64-bit
rails, original-source preservation, oversized Float128 diagnostics, missing
rates, full/selected channel budgets, pause/mute/stop, underrun and queued-block
invariants. Default retained output storage is bounded by **1 MiB**, including
preallocated conversion scratch; wide sources can use one selected channel.
Pyrefly reports **zero errors**, one existing suppression; Ruff lint/format
(**558 files**) and diff whitespace pass. No GUI behavior or device output is
introduced by this foundation. Device lifecycle, actual playback/listening,
native controls, cross-file audio comparisons and M14.3 exit gates remain open.

Before device acceptance, use the established 10-minute stereo **48 kHz WAV**
and selected compressed-array fixtures. Require at most **1 MiB retained output
buffers**, fresh-process peak RSS increase under **96 MiB** including fixture
creation, selected-record source preservation and release of decoder/array/device
resources after stop/seek/closure. Known local WAV startup should take at most
**2 s**, and acknowledged pause/stop/seek should take at most **300 ms**, with
device latency recorded separately. Source/device errors must appear without
claiming stopped output while closure is still running. Native frames retain
the **33 ms** p95 target. These gates remain open until measured.

### Original-rate output-device lifecycle foundation (2026-10-08)

A single lazy playback worker now owns one decoder/array lease and one output
device. Rapid play/seek commands coalesce to the latest source; replacement waits
for the old device to close. Pause/volume affect the existing bounded output
buffer, while seeking reopens the source at an original frame and preserves
paused state. Scoped stop ignores unrelated file owners. Stop/close show pending
closure until the worker confirms release. Changed-source, missing-device,
start/disconnection and callback errors retire output and report a diagnostic;
an unconfirmed closure prevents a pending replacement device from opening.
Initialization and idle closure never import SoundDevice or start a worker.

The [SoundDevice stream contract](https://python-sounddevice.readthedocs.io/en/0.5.6/api/streams.html)
is isolated behind typed output interfaces. Source reads and conversion stay on
the worker; callbacks consume preallocated ring/scratch arrays without file IO
or waiting for the producer. The adapter requests Float32 output at the original
sample rate and rejects an API-reported rate change. Device/host conversion
beyond the application's output API is not inferred. The cursor reports original
frames submitted to the device, with device latency exposed separately.

**23 focused playback tests** and **94 focused audio tests** pass, covering
gain/pause/mute, exact selected-channel/end padding, seek/source identity,
coalesced replacements, slow closure acknowledgement, device failures,
in-flight read cancellation, changed assets and one compressed-member lease.
Oversized array data returns to zero retained disk after stop, and close removes
temporary paths without changing source bytes. Pyrefly reports **zero errors**,
one existing suppression; Ruff lint/format (**563 files**) and diff whitespace
pass. No GUI behavior changes in this worker/device foundation.

An explicit generated two-second stereo **48 kHz** tone completes on the
reference Linux output **HDA NVidia: HDMI 0 (hw:0,3)** with **96,000 original
frames**, zero underruns and released output storage/device. The subsequent
fresh-process `scripts/audio_playback_smoke.py` lifecycle run uses quiet generated
440/660/880 Hz sections: cold startup **1.924 s**, stable pause **100.19 ms**,
paused seek to original frame **96,000** **5.16 ms**, acknowledged stop/closure
**5.11 ms**, reported device latency **10.67 ms**, **73,728 retained output
bytes**, zero bytes after stop and zero underruns. Source hashes are unchanged;
see [device lifecycle evidence](evidence/phase14/audio-output-lifecycle.json).
It uses the previously established temporary PortAudio runtime through
`LD_LIBRARY_PATH`; it does not install system packages. These are actual device
and submitted-cursor checks, with no listening observation claimed. Native GUI
controls, full fixture resource measurements, actual listening/volume
observations, comparisons and M14.3 completion remain open.

### Explicit native listening controls and idle restoration (2026-10-08)

Inspect now exposes explicit Play/Resume, Pause, Stop, source-time Seek, volume,
selected-range/all-record and selected-channel/original-channel controls beside
supporting columns. Output discovery is an explicit background command; choices
use device and host-API names rather than transient numeric indices. One editor
output worker is shared by file and mapped-record views. Switching tabs/views,
changing the focused record, revision, source/range/channel/rate/device recipe,
or closing its owner stops that output; closing an unrelated tab does not.
Volume changes affect the running buffer. Array leases and device closure remain
worker-owned, and the GUI reports pending stop until closure is acknowledged.

Listening preferences persist independently for each file/view, including
output, gain, range/channel choice and seek frame. Legacy audio recipes receive
safe defaults. Loading/restoring does not import SoundDevice, enumerate devices,
create a playback worker, prepare samples/profiles, or start output. Array record
views borrow their owner's player; they cannot close another tab's output.

`scripts/audio_listening_smoke.py` exercises genuine native button, checkbox,
slider-text, combo and seek input returns on a two-second **8 kHz** stereo WAV
and a sorted three-record compressed NPZ with aligned supporting labels. Both
select channel 2, original frames **4,000–12,000**, output **Default Sink,
PulseAudio**, volume **0.250**, pause with a stable cursor, paused seek to frame
**6,000**, volume **0.125**, resume, acknowledged stop and saved preferences.
The NPZ stays associated with original row **1** and supporting label **1**.
The actual output buffers retain **36,864 bytes**, then release; both runs have
zero observed underruns and unchanged source hashes. PortAudio reports this
PulseAudio stream's latency as **0 ms**; that API value does not establish
physical output latency or audibility.

Fresh subprocesses restore the saved recipes with visible playback controls,
no stream or output query, and no prepared signal/profile. File native save/
restore frame p95 is **11.99/11.93 ms** over **607/92 frames**; array p95 is
**13.28/12.57 ms** over **642/115 frames**. See
[file control evidence](evidence/phase14/audio-listening-file-native.json),
[file restored controls](evidence/phase14/audio-listening-file-restored.png),
[array control evidence](evidence/phase14/audio-listening-array-native.json) and
[array restored controls](evidence/phase14/audio-listening-array-restored.png).
These are native device/control observations; actual listening remains open.

Regression `audio_spectrum_smoke.py` passes native waveform/FFT/raster and fresh
restore with **18.91/19.80 ms** p95 over **708/113 frames**. The mapped-array
sample/profile regression `audio_inspect_smoke.py --array` passes native exact
controls, original row/support alignment and idle restoration with
**12.09/11.98 ms** p95 over **391/46 frames**. Focused audio, editor, workspace
and media checks pass **118 tests in 4.26 s**; Pyrefly reports zero errors and one
existing suppression. Ruff lint/format (**570 files**), offline lock consistency
and diff whitespace pass. Full playback fixture
resource acceptance, actual listening/volume observations, cross-file audio
comparisons and M14.3 completion remain open.
