"""Environment-driven configuration.

The payout wallet is NEVER hardcoded: the app refuses to start until
X402_PAY_TO holds a real address. This is deliberate — a placeholder
default would silently route real money nowhere.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Owner-configured payout wallet (set by the user 2026-10-06).
# Keep this overridable via X402_PAY_TO env var — config value, not buried constant.
OWNER_WALLET = "0x097f9685D1e0752bF8B02d61E5Ce9be7eA0FBA7F"  # Base — OpenTask payout wallet

PLACEHOLDER_WALLETS = {
    "",
    "0x0000000000000000000000000000000000000000",
    "0xTODO_REPLACE_WITH_OWNER_WALLET",
    "TODO",
}

BASE_MAINNET = "eip155:8453"
BASE_SEPOLIA = "eip155:84532"

# Public facilitator: testnets only (Base Sepolia, Solana devnet, ...).
# Mainnet (Base) requires the CDP facilitator + API keys (owner step).
PUBLIC_FACILITATOR_URL = "https://x402.org/facilitator"
CDP_FACILITATOR_URL = "https://api.cdp.coinbase.com/platform/v2/x402"


@dataclass(frozen=True)
class Settings:
    pay_to: str
    price_usdc: str  # e.g. "$0.02" — string format the x402 SDK expects
    network: str
    facilitator_url: str
    use_cdp: bool
    cdp_api_key_id: str | None
    cdp_api_key_secret: str | None
    service_name: str
    fetch_timeout_s: float
    max_fetch_bytes: int
    default_summary_sentences: int
    port: int


def load_settings() -> Settings:
    # Owner-configured default (his OpenTask payout wallet on Base).
    # Overridable per-environment via X402_PAY_TO — still a config value.
    pay_to = os.environ.get("X402_PAY_TO", OWNER_WALLET).strip()
    if pay_to in PLACEHOLDER_WALLETS:
        raise RuntimeError(
            "X402_PAY_TO is set to a placeholder address. "
            "Set it to a real wallet (see .env.example) before starting. "
            "Paid calls would otherwise have nowhere to settle."
        )
    if not (pay_to.startswith("0x") and len(pay_to) == 42):
        raise RuntimeError(f"X402_PAY_TO does not look like an EVM address: {pay_to!r}")

    network = os.environ.get("X402_NETWORK", BASE_MAINNET).strip()
    cdp_key_id = os.environ.get("CDP_API_KEY_ID", "").strip() or None
    cdp_key_secret = os.environ.get("CDP_API_KEY_SECRET", "").strip() or None

    # Facilitator selection is network-aware:
    #  - Base mainnet  -> CDP facilitator (needs API keys from portal.cdp.coinbase.com)
    #  - Testnets      -> public x402.org facilitator (no keys, free end-to-end testing)
    # An explicit X402_FACILITATOR_URL overrides the default choice.
    explicit_facilitator = os.environ.get("X402_FACILITATOR_URL", "").strip()
    use_cdp = False
    if explicit_facilitator:
        facilitator_url = explicit_facilitator
        use_cdp = "api.cdp.coinbase.com" in facilitator_url and bool(cdp_key_id)
    elif network == BASE_MAINNET:
        if not (cdp_key_id and cdp_key_secret):
            raise RuntimeError(
                "Base mainnet (eip155:8453) requires the Coinbase CDP facilitator, "
                "which needs API keys. Create a free key at "
                "https://portal.cdp.coinbase.com and set CDP_API_KEY_ID / "
                "CDP_API_KEY_SECRET — or set X402_NETWORK=eip155:84532 to test "
                "end-to-end on Base Sepolia with the public facilitator (no keys)."
            )
        facilitator_url = CDP_FACILITATOR_URL
        use_cdp = True
    else:
        facilitator_url = PUBLIC_FACILITATOR_URL

    return Settings(
        pay_to=pay_to,
        price_usdc=os.environ.get("X402_PRICE_USDC", "$0.02").strip(),
        network=network,
        facilitator_url=facilitator_url,
        use_cdp=use_cdp,
        cdp_api_key_id=cdp_key_id,
        cdp_api_key_secret=cdp_key_secret,
        service_name=os.environ.get("X402_SERVICE_NAME", "extractr").strip(),
        fetch_timeout_s=float(os.environ.get("X402_FETCH_TIMEOUT_S", "20")),
        max_fetch_bytes=int(os.environ.get("X402_MAX_FETCH_BYTES", "2000000")),
        default_summary_sentences=int(os.environ.get("X402_SUMMARY_SENTENCES", "5")),
        port=int(os.environ.get("PORT", "8000")),
    )
