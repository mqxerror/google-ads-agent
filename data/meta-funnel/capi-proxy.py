"""
Meta Conversions API (CAPI) Proxy Endpoint
==========================================
Receives events from the GTM CAPI Relay tag (08-capi-relay.html)
and forwards them to Meta's Conversions API with server-side enrichment.

Deployment options:
  1. Cloudflare Worker (recommended — lowest latency)
  2. AWS Lambda + API Gateway
  3. Self-hosted on mercan server (e.g., FastAPI behind Nginx)

This file is a standalone FastAPI app. Deploy as a separate service.
Do NOT add to the google-ads-agent backend — different concern.

Environment variables required:
  META_PIXEL_ID=584590286928383
  META_ACCESS_TOKEN=<your_system_user_token>
  CAPI_PROXY_SECRET=<shared_secret_for_auth>  (REQUIRED — passed as ?token= query param)
"""

import os
import hashlib
import hmac
import json
import time
from typing import Optional

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Meta CAPI Proxy", docs_url=None, redoc_url=None)

# CORS — allow mercan.com origins only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.mercan.com",
        "https://mercan.com",
    ],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

PIXEL_ID = os.environ.get("META_PIXEL_ID", "584590286928383")
ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
CAPI_PROXY_SECRET = os.environ.get("CAPI_PROXY_SECRET", "")
META_API_VERSION = "v20.0"
META_API_URL = f"https://graph.facebook.com/{META_API_VERSION}/{PIXEL_ID}/events"

# Allowed origins for CAPI requests
ALLOWED_ORIGINS = {"https://www.mercan.com", "https://mercan.com"}

# ── Standard event names that Meta will BLOCK (pixel is flagged) ──
BLOCKED_STANDARD_EVENTS = {
    "Lead", "CompleteRegistration", "Schedule", "SubmitApplication",
    "Contact", "Purchase", "AddToCart", "InitiateCheckout",
    "ViewContent", "Search", "Subscribe",
}


@app.post("/meta-events")
async def receive_event(request: Request):
    """
    Receives a single event from the GTM CAPI relay tag,
    enriches it with server-side data, and forwards to Meta CAPI.
    """
    # ── AUTH: Origin check ──
    origin = request.headers.get("origin", "")
    if origin and origin not in ALLOWED_ORIGINS:
        return Response(status_code=403, content="Forbidden: invalid origin")

    # ── AUTH: Shared secret (query param — sendBeacon can't send custom headers) ──
    if CAPI_PROXY_SECRET:
        token = request.query_params.get("token", "")
        if not hmac.compare_digest(token, CAPI_PROXY_SECRET):
            return Response(status_code=403, content="Forbidden: invalid token")

    try:
        body = await request.json()
    except Exception:
        return Response(status_code=400, content="Invalid JSON")

    event_name = body.get("event_name", "")
    event_id = body.get("event_id", "")

    # ── SAFETY: Block standard event names ──
    if event_name in BLOCKED_STANDARD_EVENTS:
        return Response(
            status_code=422,
            content=json.dumps({
                "error": f"Blocked standard event: {event_name}. Use custom names only.",
                "blocked_event": event_name,
            }),
            media_type="application/json",
        )

    if not event_name or not event_id:
        return Response(status_code=400, content="Missing event_name or event_id")

    # ── Server-side enrichment ──
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.client.host if request.client else ""

    user_agent = body.get("client_user_agent", request.headers.get("user-agent", ""))

    # Build the CAPI event payload
    event_data = {
        "event_name": event_name,
        "event_time": body.get("event_time", int(time.time())),
        "event_id": event_id,  # Same as browser pixel for dedup
        "event_source_url": body.get("event_source_url", ""),
        "action_source": "website",
        "user_data": {
            **body.get("user_data", {}),
            # Server-side fields (not available client-side)
            "client_ip_address": client_ip,
            "client_user_agent": user_agent,
        },
        "custom_data": body.get("custom_data", {}),
    }

    # Add fbc/fbp if present
    fbc = body.get("fbc", "")
    fbp = body.get("fbp", "")
    if fbc:
        event_data["user_data"]["fbc"] = fbc
    if fbp:
        event_data["user_data"]["fbp"] = fbp

    # ── Forward to Meta CAPI ──
    capi_payload = {
        "data": [event_data],
        "access_token": ACCESS_TOKEN,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(META_API_URL, json=capi_payload)
            meta_response = resp.json()
        except Exception as e:
            meta_response = {"error": str(e)}

    return Response(
        status_code=200,
        content=json.dumps({
            "status": "ok",
            "event_name": event_name,
            "event_id": event_id,
            "meta_response": meta_response,
        }),
        media_type="application/json",
    )


@app.get("/health")
async def health():
    return {"status": "ok", "pixel_id": PIXEL_ID, "has_token": bool(ACCESS_TOKEN)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8787)
