"""Every demo example must be a valid form submission: in range and on the field's step, or the
browser marks the input invalid and blocks "Predict"."""

import math

from app.features import FIELDS_BY_NAME, NUMERIC_FEATURES
from app.model import get_samples


def test_sample_values_fit_their_form_fields():
    for sample in get_samples():
        for name in NUMERIC_FEATURES:
            field, value = FIELDS_BY_NAME[name], float(sample["inputs"][name])
            assert field.minimum is not None and field.maximum is not None and field.step
            assert field.minimum <= value <= field.maximum, (sample["title"], name)
            steps = (value - field.minimum) / field.step
            assert math.isclose(steps, round(steps), abs_tol=1e-6), (sample["title"], name, value)
