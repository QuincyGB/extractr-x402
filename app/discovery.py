"""Agent-discovery surfaces: x402 manifest, skill.md, llms.txt.

Indexers (x402scan, Bazaar, agentic.market) read these alongside the
live 402 responses, so they must stay consistent with main.py pricing.
"""

from __future__ import annotations

from .config import Settings, NETWORK_LABELS, BASE_MAINNET


# x402 v2 "exact"-scheme asset for USDC (6 decimals). This is the canonical
# asset address the x402 SDK puts in the live 402 payment-required challenge.
USDC_ASSET = "0x3600000000000000000000000000000000000000"


def _price_to_units(price_usdc: str) -> str:
    """'$0.02' -> '20000' (USDC smallest units, 6 decimals)."""
    return str(int(round(float(price_usdc.replace("$", "").strip()) * 1_000_000)))


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
                "description": (
                    "Turn any public web page into clean readable text + "
                    "extractive summary as JSON. Returns title, markdown-ready "
                    "text, word count and summary. Built for AI research agents "
                    "— no API key, no signup, $0.02 USDC per call."
                ),
                "tags": ["extraction", "research", "web-scraping", "summarization", "agents"],
                # accepts[] mirrors the live 402 challenge so directory
                # validators (Agent Bazaar, x402scan) accept the manifest.
                # Arc + Base: same wallet, same price, buyer picks a network.
                "accepts": [
                    {
                        "scheme": "exact",
                        "network": net,
                        "amount": _price_to_units(settings.price_usdc),
                        "asset": USDC_ASSET,
                        "payTo": settings.pay_to,
                        "maxTimeoutSeconds": 300,
                    }
                    for net in dict.fromkeys((settings.network, BASE_MAINNET))
                ],
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
