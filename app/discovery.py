"""Agent-discovery surfaces: x402 manifest, skill.md, llms.txt.

Indexers (x402scan, Bazaar, agentic.market) read these alongside the
live 402 responses, so they must stay consistent with main.py pricing.
"""

from __future__ import annotations

from .config import Settings, NETWORK_LABELS


def x402_manifest(settings: Settings, base_url: str) -> dict:
    return {
        "x402Version": 2,
        "service": settings.service_name,
        "description": (
            "Extract clean readable text + extractive summary from any public "
            "web page. POST a URL, get back title, markdown-ready text, word "
            "count, and a summary. Built for AI agents doing research."
        ),
        "network": settings.network,
        "payTo": settings.pay_to,
        "resources": [
            {
                "resource": f"{base_url}/v1/extract",
                "method": "POST",
                "price": settings.price_usdc,
                "scheme": "exact",
                "mimeType": "application/json",
                "description": "Extract page text + summary (paid)",
                "inputSchema": {
                    "type": "object",
                    "required": ["url"],
                    "properties": {
                        "url": {"type": "string", "description": "Public http(s) URL to extract"},
                        "summary_sentences": {
                            "type": "integer",
                            "default": 5,
                            "description": "Sentences in the extractive summary (1-20)",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Optional cap on returned text length",
                        },
                    },
                },
            },
            {
                "resource": f"{base_url}/quote",
                "method": "GET",
                "price": "$0.00",
                "description": "Free price quote for the paid endpoint",
            },
        ],
    }


def skill_md(settings: Settings, base_url: str) -> str:
    chain = NETWORK_LABELS.get(settings.network, settings.network)
    return f"""# {settings.service_name} — paid web page extraction (x402)

Turn any public web page into clean text + summary. Pay {settings.price_usdc} USDC
per call on {chain} (`{settings.network}`) via the x402 protocol — no API key needed.

## Paid endpoint

`POST {base_url}/v1/extract`

Body (JSON):
- `url` (required): public http(s) URL
- `summary_sentences` (optional, 1-20, default 5)
- `max_chars` (optional): cap returned text length

Returns: `title`, `text`, `summary`, `word_count`, `char_count`, `final_url`.

Pay with any x402 v2 client (e.g. `x402-fetch`): call the endpoint, get a 402
challenge, sign, retry with the payment header. Settlement is USDC on {chain}.

## Free endpoints

- `GET {base_url}/quote` — current price, network, payTo
- `GET {base_url}/health` — liveness
- `GET {base_url}/.well-known/x402` — machine-readable manifest
"""


def llms_txt(settings: Settings, base_url: str) -> str:
    return f"""# {settings.service_name}

Paid API: extract clean text + extractive summary from any public web page.
Price: {settings.price_usdc} USDC per call, x402 v2, network {settings.network}.

## Endpoints

- POST {base_url}/v1/extract — paid. Body: {{"url": str, "summary_sentences"?: int, "max_chars"?: int}}
- GET {base_url}/quote — free price quote
- GET {base_url}/health — free liveness check
- GET {base_url}/.well-known/x402 — manifest
"""
