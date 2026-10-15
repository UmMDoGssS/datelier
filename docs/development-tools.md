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

Step 2 has not started.

The listening, Titanic usability, accelerated-rendering and other-platform
limitations remain unchanged. Phase evidence and raw reports are historical
records, not the current development command inventory.
