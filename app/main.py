import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
)

_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # API Gateway puts the caller's address first in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")


@app.middleware("http")
async def guard(request: Request, call_next):  # noqa: ANN001, ANN201 - Starlette signature
    """Reject oversized bodies and over-eager clients before any model work happens."""
    length = request.headers.get("content-length")
    if length is not None and (not length.isdigit() or int(length) > settings.MAX_BODY_BYTES):
        return JSONResponse({"detail": "Request body too large."}, status_code=413)

    if request.method == "POST":
        now = time.monotonic()
        window = _hits[_client_ip(request)]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= settings.RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                {"detail": "Too many requests, please slow down."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        window.append(now)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
    max_age=600,
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get(f"{settings.API_V1_STR}/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
