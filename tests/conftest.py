import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import _hits, app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client() -> TestClient:
    _hits.clear()
    return TestClient(app)


@pytest.fixture
def sample_inputs() -> dict:
    samples = json.loads((ROOT / "app" / "model_artifacts" / "samples.json").read_text())
    return dict(samples[0]["inputs"])
