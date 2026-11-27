"""AWS Lambda entry point: Mangum adapts API Gateway HTTP API (v2) events to the FastAPI `app`,
so the same app runs locally (`fastapi dev`) and on Lambda."""

from mangum import Mangum

from app.main import app

handler = Mangum(app)
