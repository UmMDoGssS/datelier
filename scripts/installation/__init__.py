"""Verify installed-wheel text and mixed-modality workflows outside the checkout.

Build with ``uv build``. One locked local installation workflow is::

    UV_PROJECT_ENVIRONMENT=/tmp/datelier uv sync --locked --no-dev --no-install-project
    uv pip install --python /tmp/datelier/bin/python --no-deps dist/datelier-*.whl
    uv pip check --python /tmp/datelier/bin/python

Copy the entire scripts package to a temporary directory outside the checkout;
from there run ``/tmp/datelier/bin/python -m scripts.installation.text``
or scripts.installation.multimodal. The probes assert that Datelier resolves to
site-packages. Add --extra checkpoints when syncing and --checkpoints to the mixed
probe only for CPU-extra verification. Native display, codec, and PortAudio
requirements still apply. A wheel/module check alone is not a clean-install gate.
"""
