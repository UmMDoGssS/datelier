# Development verification tools

Run these repository-only tools from the checkout root with `uv run python -m`.
They are not installed as part of Datelier. Application code lives in
`src/datelier/`; ordinary automated behavioral tests live in `tests/`.

| Package | Purpose |
| --- | --- |
| `gui` | Current native interaction, rendering and fresh-process restoration checks |
| `benchmarks` | Timing, memory, responsiveness and source-preservation measurements |
| `environment` | Codec, optional CPU checkpoint and actual audio-device probes |
| `installation` | Installed-wheel text and mixed-modality checks |
| `support` | Shared fixtures, native input/motion and benchmark instrumentation |

## Native acceptance

A Linux graphical session is required. Checks run serially because they drive
native input. Preview the complete inventory without opening windows:

```sh
uv run python -m scripts.gui.acceptance --list --matrix
```

Run the base inventory or add the three-size/three-theme matrix:

```sh
uv run python -m scripts.gui.acceptance
uv run python -m scripts.gui.acceptance --matrix --output /tmp/datelier-native
```

The runner selects Mesa software rendering and eight Polars threads. It writes
per-command logs and `native-acceptance.json`. Resume an interrupted run with
`--resume` and the same options/output directory. Reports from the old flat
runner cannot be resumed by the new inventory.

Run an individual check as a module:

```sh
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run python -m scripts.gui.tabs
LIBGL_ALWAYS_SOFTWARE=1 POLARS_MAX_THREADS=8 uv run python -m scripts.gui.workspace
```

Every executable module in `gui` belongs to the default inventory, including
analysis schemas and the media matrix. The full matrix repeats workbench/media
checks at each size and theme; the distinct-source annotation variant also runs.
Real output-device probes live in `environment`, outside automatic GUI acceptance.

## Benchmarks and environment checks

For example:

```sh
POLARS_MAX_THREADS=8 uv run python -m scripts.benchmarks.inspection
POLARS_MAX_THREADS=8 uv run python -m scripts.benchmarks.formats
uv run python -m scripts.environment.audio_codecs --output /tmp/audio-codecs.json
uv run --extra checkpoints python -m scripts.environment.checkpoints
uv run python -m scripts.environment.audio_playback --output /tmp/audio-output.json
```

Benchmarks retain their existing settings and resource assertions. Some open
native windows or generate large temporary datasets; inspect the module's options
and docstring before selecting a run. The codec probe uses FFmpeg to generate an
independent MP3 fixture. The audio playback probe explicitly uses a real output
device; automatic GUI checks use deterministic injected devices.

## Installed-wheel checks

Build a wheel and install it into a separate environment. Copy this entire
`scripts/` package into a temporary directory outside the checkout, then run from
that directory using the installed environment's Python:

```sh
/path/to/installed/bin/python -m scripts.installation.text
/path/to/installed/bin/python -m scripts.installation.multimodal --output /tmp/installed-mixed.json
```

Use `--checkpoints` for the mixed probe only when that environment includes the
optional CPU checkpoint dependencies. The usual Linux codec and PortAudio
runtime requirements still apply. These probes assert that Datelier resolves
to `site-packages`; copying the development package preserves shared fixtures
without adding them to the application wheel.

## Retired tools

The 2026-10-15 cleanup removed the `--feasibility` command and its synthetic
GUI/analysis/scatter implementation, three dedicated scripts, the unused old audio
widget-patching helper and two early texture prerequisite probes. Shared table
and multimodal fixtures remain in `support` for current consumers.

Historical phase reports retain their original commands and measurements; use
the matching historical checkout to reproduce them. Current replacement paths
are described in [the harness audit](../docs/gui-harness-audit.md). Cleanup scope
and actual verification are recorded in
[development-tools.md](../docs/development-tools.md).
