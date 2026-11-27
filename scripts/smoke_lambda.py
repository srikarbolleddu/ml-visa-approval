"""Smoke-test the Lambda image locally via the runtime emulator, using API Gateway v2 events.

docker run -d -p 9000:8080 <image> && python3 scripts/smoke_lambda.py http://localhost:9000
"""

import json
import sys
import time
import urllib.request

URL = sys.argv[1].rstrip("/") + "/2015-03-31/functions/function/invocations"


def event(method: str, path: str, body: dict | None = None) -> dict:
    payload = json.dumps(body) if body is not None else ""
    headers = {"host": "localhost", "x-forwarded-for": "1.2.3.4"}
    if body is not None:
        headers.update({"content-type": "application/json", "content-length": str(len(payload))})
    http = {"method": method, "path": path, "sourceIp": "1.2.3.4", "protocol": "HTTP/1.1"}
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": headers,
        "requestContext": {"http": {**http, "userAgent": "smoke"}, "stage": "$default"},
        "body": payload,
        "isBase64Encoded": False,
    }


def invoke(ev: dict) -> dict:
    last_error: Exception | None = None
    for _ in range(30):  # the emulator takes a few seconds to come up
        try:
            request = urllib.request.Request(URL, data=json.dumps(ev).encode())
            with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310
                return json.load(response)
        except OSError as error:
            last_error = error
            time.sleep(1)
    raise SystemExit(f"Lambda emulator did not respond: {last_error}")


def main() -> None:
    samples = json.loads(invoke(event("GET", "/api/v1/samples"))["body"])
    inputs = samples[0]["inputs"]
    checks = {
        "health": invoke(event("GET", "/api/v1/health"))["statusCode"] == 200,
        "schema": invoke(event("GET", "/api/v1/schema"))["statusCode"] == 200,
        "explore": invoke(event("GET", "/api/v1/explore"))["statusCode"] == 200,
        "predict": invoke(event("POST", "/api/v1/predict", inputs))["statusCode"] == 200,
        "predict rejects bad input": invoke(
            event("POST", "/api/v1/predict", {**inputs, "age": 500})
        )["statusCode"]
        == 422,
    }
    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not all(checks.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
