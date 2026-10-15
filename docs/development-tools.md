# Development tool cleanup

Authorized on 2026-10-15: retire the historical synthetic feasibility command
and implementation, remove obsolete prerequisite probes, and organize the
remaining verification tools by responsibility. Historical phase evidence is
retained; old commands require the matching historical checkout.

## Delivery steps

1. Remove `--feasibility`, its synthetic GUI/analysis/plot implementations and
   dedicated checks. Retain reusable deterministic table and multimodal fixtures
   as repository-only development support, outside the installed application.
   Retire the unused old widget-patching audio helper and the two early texture
   prerequisite probes. Current image/GUI checks cover the application paths.
2. Group retained GUI checks, benchmarks, environment probes, installation checks
   and shared support into packages. Use module commands, including in child
   processes, so imports do not depend on a flat script directory. Update the
   active command inventory, run the full suite and native acceptance, and verify
   wheel contents.

## Verification

Step 1 passes: **18 focused tests** (CLI argument rejection, shared fixture
invariants, mixed-session handling and image controls), Pyrefly with zero errors
(one existing suppression and 37 warnings), Ruff lint/format and whitespace
checks. The current CLI renders **20 native Mesa frames**. The first launch was
blocked by sandbox display access; the same command passes with local display
access. No production imports of `datelier.feasibility` remain.

Step 2 groups **72 retained modules** into `gui`, `benchmarks`, `environment`,
`installation` and `support`, removes obsolete filename prefixes, and documents
module entry points in [scripts/README.md](../scripts/README.md). Shared fake audio
devices move out of the test directory; native checks no longer modify
`sys.path`. Fresh-process restore and benchmark children use `python -m`.

The native runner now discovers every executable GUI module, including the
previously omitted analysis-schema check and the media matrix in its base run.
`--list` previews commands without importing the app or GUI. Existing resume/log
behavior is retained, with mismatched inventory reports rejected. The format
benchmark now selects only the five tabular formats its fixture writer supports;
it previously included newer media/object/array enum values by accident.

Step 2 verification:

- **1,208 tests pass** (three dependency warnings), including real subprocess
  benchmark runs for inspection, all five tabular formats, transforms and
  exploration using small deterministic fixtures, and a GUI-free inventory check.
- Pyrefly reports **zero errors** (one existing suppression, 37 warnings); Ruff
  lint/format and diff whitespace checks pass.
- The **70 other relocated modules preserve their bodies**, after normalizing
  import changes, removal of the two test-path insertions and child module calls.
- Source distribution and wheel build successfully. The wheel contains 659 files
  and contains neither `datelier.feasibility` nor the development tools.
- The installed CLI help, installed-wheel text probe and relocated CPU checkpoint
  probe pass. Wheel checks run outside the checkout with a copied `scripts`
  package and the existing development dependency directory on `PYTHONPATH`;
  they resolve Datelier from the separate wheel installation. A clean dependency
  installation could not resolve uncached ImGui Bundle offline, so no new clean
  base/CPU installation gate is claimed.
- The installed mixed-media probe reaches real device discovery but cannot finish
  because the current environment lacks Linux PortAudio. Native audio checks use
  deterministic injected devices. Real-device/codec probe execution remains
  unverified in this cleanup; no system dependencies were installed.
- Current Markdown links resolve. Historical commands and raw evidence remain
  intact; current runnable commands are centralized in the development guide.

The native inventory and full size/theme matrix pass: **56/56 commands**,
406.9 seconds total, including actual native input, separate-process restore,
all three window sizes and Dark/Light/Classic themes under Mesa. The report and
per-command logs are at `/tmp/datelier-tools-native/`. The command was
`uv --cache-dir /tmp/datelier-uv-cache run --offline --no-sync python -m scripts.gui.acceptance --matrix --output /tmp/datelier-tools-native`
with local display access.

Both cleanup delivery gates pass. The change removes a net **866 lines of Python**;
`__init__.py` and the guide are the only top-level files in `scripts/`. The
optional hardware/runtime and fresh dependency-install limitations above remain
explicit; this cleanup does not claim new acceptance for those environments.

The listening, Titanic usability, accelerated-rendering and other-platform
limitations remain unchanged. Phase evidence and raw reports are historical
records, not the current development command inventory.
