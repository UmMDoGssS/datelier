"""Profile/plot selection and settings coordinated outside rendering callbacks.

Profiles allow a numeric group or one categorical/temporal/text field; role-aware
pickers keep this policy distinct from analysis feature selection. Changes
request worker preparation and preserve saved settings where compatible.
Single-column count bars route to Profiles; category/value distributions and
grouped counts belong to Relationships.
"""

from datelier.application.exploration.axes import AxisScale as AxisScale
from datelier.application.exploration.axes import AxisState as AxisState
from datelier.application.exploration.axes import Range as Range
from datelier.application.exploration.axes import Ranges as Ranges
from datelier.application.exploration.axes import validate_range as validate_range
from datelier.application.exploration.plots import PlotState as PlotState
from datelier.application.exploration.profiles import (
    ProfileController as ProfileController,
)
from datelier.application.exploration.profiles import ProfileFamily as ProfileFamily
