"""Experience-layer API gateway: JWT passthrough, routing, rate limits."""
from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from hub.security import limiter

UPSTREAM = os.environ.get("HUB_UPSTREAM", "http://127.0.0.1:8080")

app = FastAPI(title="Integration Hub Gateway", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

ROUTES = {
    "/system": "/system",
    "/process": "/process",
    "/experience": "/experience",
    "/auth": "/auth",
    "/health": "/health",
    "/metrics": "/metrics",
    "/docs": "/docs",
    "/openapi.json": "/openapi.json",
}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request) -> Response:
    client = request.client.host if request.client else "anon"
    limiter.check(f"gw:{client}")
    url = f"{UPSTREAM}/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in {"host", "content-length"}}
    body = await request.body()
    async with httpx.AsyncClient(timeout=30.0) as client_http:
        upstream = await client_http.request(request.method, url, headers=headers, content=body)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={"x-gateway": "integration-hub", **{k: v for k, v in upstream.headers.items() if k.lower() == "content-type"}},
    )
