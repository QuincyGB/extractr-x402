"""Extractr — x402 pay-per-call web content extraction API.

Paid:   POST /v1/extract   (USDC via x402 v2 "exact" scheme; chain from X402_NETWORK)
Free:   GET  /health, /quote, /.well-known/x402, /skill.md, /llms.txt
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption, RouteConfig
from x402.http.middleware import fastapi_payment_middleware
from x402.mechanisms.evm.exact.server import ExactEvmScheme
from x402.server import x402ResourceServer

from .config import load_settings
from .discovery import llms_txt, skill_md, x402_manifest
from .extractor import FetchError, fetch_and_extract

log = logging.getLogger("extractr")
logging.basicConfig(level=logging.INFO)


def _sanitize_proxy_env() -> None:
    """Drop bracketed-IPv6 entries from no_proxy.

    Some httpx versions raise InvalidURL on entries like "[::1]" when
    building proxy mounts. This is an environment quirk (seen in sandboxed
    VMs); harmless elsewhere since plain "::1" still matches.
    """
    for var in ("no_proxy", "NO_PROXY"):
        val = __import__("os").environ.get(var)
        if not val:
            continue
        cleaned = ",".join(
            p for p in val.split(",") if not (p.startswith("[") and p.endswith("]"))
        )
        __import__("os").environ[var] = cleaned


_sanitize_proxy_env()

settings = load_settings()  # raises if payout wallet is a placeholder

# --- x402 wiring -------------------------------------------------------------
# Facilitator is network-aware (see config.py):
#   Base mainnet  -> CDP facilitator (needs CDP_API_KEY_ID/SECRET)
#   Arc mainnet   -> ultravioletadao public facilitator (no keys)
#   Base Sepolia  -> public x402.org facilitator (no keys)
if settings.use_cdp:
    from .cdp_auth import cdp_facilitator_config

    assert settings.cdp_api_key_id and settings.cdp_api_key_secret
    facilitator = HTTPFacilitatorClient(
        cdp_facilitator_config(settings.cdp_api_key_id, settings.cdp_api_key_secret)
    )
    log.info("facilitator: CDP (Base mainnet)")
else:
    facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.facilitator_url))
    log.info("facilitator: %s (%s)", settings.facilitator_url, settings.network)

resource_server = x402ResourceServer(facilitator)
resource_server.register(settings.network, ExactEvmScheme())

EXTRACT_DESCRIPTION = (
    "Extract clean readable text and an extractive summary from any public web "
    "page. POST a URL; receive title, text, word count, and summary. "
    "Built for AI research agents."
)

routes = {
    "POST /v1/extract": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=settings.pay_to,
                price=settings.price_usdc,
                network=settings.network,
            )
        ],
        description=EXTRACT_DESCRIPTION,
        mime_type="application/json",
        service_name=settings.service_name,  # ≤32 chars, forwarded to Bazaar
        tags=["extraction", "research", "web", "agents"],
        extensions={
            "bazaar": {
                "info": {
                    "input": {
                        "type": "http",
                        "method": "POST",
                        "bodyType": "json",
                        "body": {
                            "url": "https://example.com/article",
                            "summary_sentences": 5,
                        },
                    },
                    "output": {
                        "type": "application/json",
                        "example": {
                            "title": "Example article",
                            "summary": "First sentence. Second sentence.",
                            "word_count": 842,
                        },
                    },
                },
                "schema": {
                    "type": "object",
                    "required": ["url"],
                    "properties": {
                        "url": {"type": "string"},
                        "summary_sentences": {"type": "integer"},
                        "max_chars": {"type": "integer"},
                    },
                },
            }
        },
    ),
}

# --- app ---------------------------------------------------------------------
app = FastAPI(title="extractr", version="1.0.0")


@app.middleware("http")
async def x402_middleware(request: Request, call_next):
    if not settings.require_payment:
        # Open mode (PayGate upstream): PayGate is the paywall, so we skip
        # the 402 challenge. When OPEN_MODE_TOKEN is set, requests must still
        # carry the shared header so random internet traffic can't use the
        # unwalled instance; when unset, the instance serves openly.
        if settings.open_mode_token:
            token = request.headers.get("x-open-token")
            if not token or token != settings.open_mode_token:
                return JSONResponse({"error": "forbidden"}, status_code=403)
        log.info(
            "open mode: payment bypassed for %s %s", request.method, request.url.path
        )
        return await call_next(request)
    return await fastapi_payment_middleware(routes, resource_server)(request, call_next)


class ExtractRequest(BaseModel):
    url: str = Field(description="Public http(s) URL to extract")
    summary_sentences: int = Field(default=5, ge=1, le=20)
    max_chars: int | None = Field(default=None, ge=500, le=100000)


@app.get("/health")
async def health():
    return {"ok": True, "service": settings.service_name}


@app.get("/quote")
async def quote():
    """Free: what the paid endpoint costs and where it settles."""
    return {
        "service": settings.service_name,
        "endpoint": "/v1/extract",
        "price": settings.price_usdc,
        "asset": "USDC",
        "network": settings.network,
        "payTo": settings.pay_to,
        "protocol": "x402 v2 (exact scheme)",
    }


@app.get("/debug")
async def debug():
    """Free: operator config WITHOUT secrets (key presence only)."""
    return {
        "service": settings.service_name,
        "network": settings.network,
        "facilitator": settings.facilitator_url,
        "use_cdp": settings.use_cdp,
        "cdp_key_configured": bool(settings.cdp_api_key_id),
        "cdp_key_prefix": (settings.cdp_api_key_id or "")[:6] or None,
        "price": settings.price_usdc,
        "payTo": settings.pay_to,
        "require_payment": settings.require_payment,
    }


@app.get("/.well-known/x402")
async def well_known(request: Request):
    base = str(request.base_url).rstrip("/")
    # Railway terminates TLS at the edge; indexers need the public https URL.
    if base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    return JSONResponse(x402_manifest(settings, base))


@app.get("/skill.md", response_class=PlainTextResponse)
async def skill(request: Request):
    base = str(request.base_url).rstrip("/")
    return skill_md(settings, base)


@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms(request: Request):
    base = str(request.base_url).rstrip("/")
    return llms_txt(settings, base)


@app.post("/v1/extract")
async def extract(req: ExtractRequest):
    """Paid endpoint — unreachable until the x402 middleware verifies payment
    (or, in open mode with REQUIRE_PAYMENT=false, directly — optionally gated
    on the X-Open-Token header when OPEN_MODE_TOKEN is set)."""
    try:
        page = await fetch_and_extract(
            req.url,
            timeout_s=settings.fetch_timeout_s,
            max_bytes=settings.max_fetch_bytes,
            summary_sentences=req.summary_sentences,
            max_chars=req.max_chars,
        )
    except FetchError as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    return {
        "url": page.url,
        "final_url": page.final_url,
        "title": page.title,
        "text": page.text,
        "summary": page.summary,
        "word_count": page.word_count,
        "char_count": page.char_count,
        "truncated": page.truncated,
    }


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.port, reload=False)


if __name__ == "__main__":
    main()
