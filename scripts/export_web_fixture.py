"""Record the API's responses into web/src/fixture.json.

The standalone demo page falls back to these recorded responses when it isn't connected to a live
API (e.g. before the AWS deploy, or if the API is down), so the page always shows something real.
Re-run after retraining: `uv run python scripts/export_web_fixture.py`.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

OUT = Path(__file__).resolve().parents[1] / "web" / "src" / "fixture.json"


def main() -> None:
    client = TestClient(app)
    samples = client.get("/api/v1/samples").json()
    fixture = {
        "schema": client.get("/api/v1/schema").json(),
        "samples": samples,
        "explore": client.get("/api/v1/explore").json(),
        "predictions": [client.post("/api/v1/predict", json=s["inputs"]).json() for s in samples],
    }
    OUT.write_text(json.dumps(fixture, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
