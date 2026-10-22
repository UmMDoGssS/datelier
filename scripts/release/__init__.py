"""Linux x86-64 PyInstaller release preparation with the CPU checkpoint extra.

Install the locked tools and build from the checkout::

    uv sync --locked --extra checkpoints --group freeze
    uv run --no-sync python -m scripts.release.build

Building requires the Ubuntu libportaudio2 runtime and its provider notice.
When it is not installed, apt-get download libportaudio2 and dpkg-deb -x can
extract it in build/frozen/system-deps; pass its usr/lib/x86_64-linux-gnu/
libportaudio.so.2 path with --portaudio-library. No system installation is needed.

The one-folder bundle is dist/frozen/datelier; keep its _internal directory
beside the executable. Ubuntu 26.04 x86-64 with glibc 2.43 is the tested build
baseline; older distributions and accelerated rendering are unverified. OpenGL
and an audio output service/device remain host responsibilities. Bundled CPU
PyTorch enables restricted checkpoint inspection without CUDA.

datelier-verify is a repository verification executable, built from the same
module/library graph. It dispatches ML workers through the actual datelier
executable. It is excluded from the release archive. Run it outside the checkout
with --output pointing to an empty temporary directory. Its checks do not close
the deferred human listening or unaided Titanic usability gates.
"""
