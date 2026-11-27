"""The demo page's offline fallback (web/src/fixture.json) must match what the API returns now.
If this fails after retraining, run: uv run python scripts/export_web_fixture.py"""

import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "web" / "src" / "fixture.json"


def test_web_fixture_matches_api(client):
    fixture = json.loads(FIXTURE.read_text())

    assert fixture["schema"] == client.get("/api/v1/schema").json()
    assert fixture["samples"] == client.get("/api/v1/samples").json()
    assert fixture["explore"] == client.get("/api/v1/explore").json()
    assert fixture["predictions"] == [
        client.post("/api/v1/predict", json=s["inputs"]).json() for s in fixture["samples"]
    ]
