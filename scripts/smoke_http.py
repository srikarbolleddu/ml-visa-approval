"""Smoke-test a deployed demo API: `python3 scripts/smoke_http.py https://<api-id>.execute-api...`"""

import json
import sys
import urllib.error
import urllib.request
from typing import Any

BASE = sys.argv[1].rstrip("/") + "/api/v1"


def call(path: str, body: dict | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE + path, data=data, headers={"content-type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def main() -> None:
    checks = []
    checks.append(("health", call("/health")[0] == 200))
    checks.append(("schema", call("/schema")[0] == 200))
    status, samples = call("/samples")
    checks.append(("samples", status == 200 and isinstance(samples, list) and len(samples) > 0))
    inputs = samples[0]["inputs"] if isinstance(samples, list) else {}
    status, prediction = call("/predict", inputs)
    checks.append(("predict", status == 200 and "score" in prediction))
    checks.append(("predict rejects bad input", call("/predict", {**inputs, "age": 500})[0] == 422))
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not all(ok for _, ok in checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
