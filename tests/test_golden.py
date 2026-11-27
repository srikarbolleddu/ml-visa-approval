"""The shipped model must reproduce the outputs recorded at training time (reports/golden.json)."""

import json
from pathlib import Path

import pytest

from app.model import get_model

GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "reports" / "golden.json").read_text())


@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: str(c["probability"]))
def test_golden_prediction(case):
    # golden.json records P(denied); the API reports the chance of certification.
    assert 1 - get_model().predict(case["inputs"])["score"] == pytest.approx(
        case["probability"], abs=1e-4
    )


def test_model_refuses_unexpected_types(tmp_path, monkeypatch):
    import skops.io as sio

    from app import model as model_io

    path = tmp_path / "evil.skops"
    sio.dump({"fn": print}, path)
    monkeypatch.setattr(model_io, "TRUSTED_TYPES", frozenset())

    with pytest.raises(RuntimeError, match="unexpected types"):
        model_io.load(path)
