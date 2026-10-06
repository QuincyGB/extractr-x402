"""Regression test: the x402 Bazaar discovery extension must be embedded in
the 402 payment-required challenge so facilitators/agentic.market can index us.

Runs the app in-process (Base Sepolia, keyless public facilitator) and
decodes the `payment-required` header of an unpaid POST /v1/extract.
"""

import base64
import json
import os

import pytest


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("X402_NETWORK", "eip155:84532")
    monkeypatch.delenv("CDP_API_KEY_ID", raising=False)
    monkeypatch.delenv("CDP_API_KEY_SECRET", raising=False)
    import importlib

    import app.main as main_mod

    importlib.reload(main_mod)
    from fastapi.testclient import TestClient

    return TestClient(main_mod.app)


def _challenge_doc(client):
    resp = client.post("/v1/extract", json={"url": "https://example.com"})
    assert resp.status_code == 402
    header = resp.headers.get("payment-required") or resp.headers.get(
        "x-payment-required"
    )
    assert header, "402 response must carry a payment-required header"
    return json.loads(base64.b64decode(header))


def test_402_challenge_carries_bazaar_extension(client):
    doc = _challenge_doc(client)
    bazaar = doc.get("extensions", {}).get("bazaar")
    assert bazaar, "bazaar extension missing from 402 challenge"
    assert "info" in bazaar and "schema" in bazaar
    assert bazaar["schema"].get("required") == ["url"]
    assert "url" in bazaar["schema"]["properties"]
    assert bazaar["info"]["input"]["method"] == "POST"


def test_402_challenge_names_owner_wallet_and_price(client):
    doc = _challenge_doc(client)
    accepts = doc.get("accepts") or []
    assert accepts, "402 challenge has no payment options"
    opt = accepts[0]
    assert opt.get("payTo") == os.environ.get(
        "X402_PAY_TO", "0x097f9685D1e0752bF8B02d61E5Ce9be7eA0FBA7F"
    )
    assert opt.get("network") == "eip155:84532"
