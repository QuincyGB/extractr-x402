"""Arc port regression tests.

Verifies that X402_NETWORK=eip155:5042 (Circle's Arc mainnet):
- resolves to the ultravioletadao public facilitator (CDP doesn't settle Arc),
- needs no CDP API keys,
- emits a 402 challenge on Arc with the owner's wallet, $0.02 price,
  Arc USDC asset, and the Bazaar discovery extension intact,
- and that Base mainnet behavior is unchanged (still requires CDP keys).

Mirrors the style of tests/test_bazaar_discovery.py (in-process app,
monkeypatched env).
"""

import base64
import importlib
import json

import pytest

from app.config import (
    ARC_FACILITATOR_URL,
    ARC_MAINNET,
    BASE_MAINNET,
    load_settings,
)

OWNER_WALLET = "0x097f9685D1e0752bF8B02d61E5Ce9be7eA0FBA7F"
ARC_USDC = "0x3600000000000000000000000000000000000000"  # Arc USDC precompile
AMOUNT_ATOMIC = "20000"  # $0.02 in 6-decimal USDC


@pytest.fixture()
def arc_env(monkeypatch):
    monkeypatch.setenv("X402_NETWORK", ARC_MAINNET)
    monkeypatch.setenv("X402_PAY_TO", OWNER_WALLET)
    monkeypatch.delenv("CDP_API_KEY_ID", raising=False)
    monkeypatch.delenv("CDP_API_KEY_SECRET", raising=False)
    monkeypatch.delenv("X402_FACILITATOR_URL", raising=False)


@pytest.fixture()
def arc_client(arc_env):
    import app.main as main_mod

    importlib.reload(main_mod)
    from fastapi.testclient import TestClient

    return TestClient(main_mod.app)


def test_arc_resolves_network_and_facilitator(arc_env):
    settings = load_settings()
    assert settings.network == ARC_MAINNET == "eip155:5042"
    assert settings.facilitator_url == ARC_FACILITATOR_URL
    assert settings.use_cdp is False
    assert settings.price_usdc == "$0.02"
    assert settings.pay_to == OWNER_WALLET


def test_arc_needs_no_cdp_keys(arc_env):
    # Must not raise even with zero CDP credentials present.
    load_settings()


def test_base_mainnet_still_requires_cdp_keys(monkeypatch):
    # Regression guard: the new Arc branch must not change Base behavior.
    monkeypatch.setenv("X402_NETWORK", BASE_MAINNET)
    monkeypatch.setenv("X402_PAY_TO", OWNER_WALLET)
    monkeypatch.delenv("CDP_API_KEY_ID", raising=False)
    monkeypatch.delenv("CDP_API_KEY_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="CDP"):
        load_settings()


def _challenge_doc(client):
    resp = client.post("/v1/extract", json={"url": "https://example.com"})
    assert resp.status_code == 402
    header = resp.headers.get("payment-required") or resp.headers.get(
        "x-payment-required"
    )
    assert header, "402 response must carry a payment-required header"
    return json.loads(base64.b64decode(header))


def test_arc_402_challenge_pays_owner_on_arc(arc_client):
    doc = _challenge_doc(arc_client)
    accepts = doc.get("accepts") or []
    assert accepts, "402 challenge has no payment options"
    opt = accepts[0]
    assert opt.get("scheme") == "exact"
    assert opt.get("network") == "eip155:5042"
    assert opt.get("payTo") == OWNER_WALLET
    assert opt.get("amount") == AMOUNT_ATOMIC
    assert opt.get("asset") == ARC_USDC
    assert opt.get("extra", {}).get("name") == "USDC"


def test_arc_402_challenge_carries_bazaar_extension(arc_client):
    doc = _challenge_doc(arc_client)
    bazaar = doc.get("extensions", {}).get("bazaar")
    assert bazaar, "bazaar extension missing from Arc 402 challenge"
    assert "info" in bazaar and "schema" in bazaar
    assert bazaar["schema"].get("required") == ["url"]
    assert "url" in bazaar["schema"]["properties"]


def test_arc_manifest_and_skill_name_arc(arc_client):
    manifest = arc_client.get("/.well-known/x402").json()
    assert manifest["network"] == "eip155:5042"
    assert manifest["payTo"] == OWNER_WALLET
    skill = arc_client.get("/skill.md").text
    assert "Arc" in skill
    assert "eip155:5042" in skill
