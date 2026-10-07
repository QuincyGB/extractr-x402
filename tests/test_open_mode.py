"""Open-mode tests (PayGate upstream use-case).

REQUIRE_PAYMENT=false lets the app skip the x402 402 challenge so a wrapping
paywall (PayGate) can be the payment layer. Behavior:
- OPEN_MODE_TOKEN set: POST /v1/extract requires header X-Open-Token matching
  it (403 otherwise).
- OPEN_MODE_TOKEN unset/empty: app starts normally (logs a warning) and serves
  /v1/extract without any header — PayGate is the paywall in that setup.
- Default behavior (REQUIRE_PAYMENT unset/true) still emits 402 on unpaid POST.

Mirrors the style of tests/test_arc_config.py (in-process app, monkeypatched
env, importlib.reload).
"""

import importlib
from types import SimpleNamespace

import pytest

from app.config import ARC_MAINNET, load_settings

OWNER_WALLET = "0x097f9685D1e0752bF8B02d61E5Ce9be7eA0FBA7F"
OPEN_TOKEN = "test-open-token-abc123"


@pytest.fixture()
def open_env(monkeypatch):
    monkeypatch.setenv("X402_NETWORK", ARC_MAINNET)
    monkeypatch.setenv("X402_PAY_TO", OWNER_WALLET)
    monkeypatch.setenv("REQUIRE_PAYMENT", "false")
    monkeypatch.setenv("OPEN_MODE_TOKEN", OPEN_TOKEN)
    monkeypatch.delenv("CDP_API_KEY_ID", raising=False)
    monkeypatch.delenv("CDP_API_KEY_SECRET", raising=False)
    monkeypatch.delenv("X402_FACILITATOR_URL", raising=False)


@pytest.fixture()
def open_client(open_env, monkeypatch):
    import app.main as main_mod

    importlib.reload(main_mod)

    async def fake_extract(url, timeout_s=None, max_bytes=None,
                           summary_sentences=5, max_chars=None):
        return SimpleNamespace(
            url=url,
            final_url=url,
            title="Example",
            text="Some extracted text.",
            summary="Some extracted text.",
            word_count=3,
            char_count=21,
            truncated=False,
        )

    monkeypatch.setattr(main_mod, "fetch_and_extract", fake_extract)
    from fastapi.testclient import TestClient

    return TestClient(main_mod.app)


@pytest.fixture()
def open_env_no_token(monkeypatch):
    monkeypatch.setenv("X402_NETWORK", ARC_MAINNET)
    monkeypatch.setenv("X402_PAY_TO", OWNER_WALLET)
    monkeypatch.setenv("REQUIRE_PAYMENT", "false")
    monkeypatch.delenv("OPEN_MODE_TOKEN", raising=False)
    monkeypatch.delenv("CDP_API_KEY_ID", raising=False)
    monkeypatch.delenv("CDP_API_KEY_SECRET", raising=False)
    monkeypatch.delenv("X402_FACILITATOR_URL", raising=False)


@pytest.fixture()
def open_client_no_token(open_env_no_token, monkeypatch):
    import app.main as main_mod

    importlib.reload(main_mod)

    async def fake_extract(url, timeout_s=None, max_bytes=None,
                           summary_sentences=5, max_chars=None):
        return SimpleNamespace(
            url=url,
            final_url=url,
            title="Example",
            text="Some extracted text.",
            summary="Some extracted text.",
            word_count=3,
            char_count=21,
            truncated=False,
        )

    monkeypatch.setattr(main_mod, "fetch_and_extract", fake_extract)
    from fastapi.testclient import TestClient

    return TestClient(main_mod.app)


def test_open_mode_settings(open_env):
    settings = load_settings()
    assert settings.require_payment is False
    assert settings.open_mode_token == OPEN_TOKEN


def test_open_mode_serves_unpaid_post_with_correct_header(open_client):
    resp = open_client.post(
        "/v1/extract",
        json={"url": "https://example.com"},
        headers={"X-Open-Token": OPEN_TOKEN},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Example"
    assert body["word_count"] == 3


def test_open_mode_403_without_header(open_client):
    resp = open_client.post("/v1/extract", json={"url": "https://example.com"})
    assert resp.status_code == 403


def test_open_mode_403_with_wrong_header(open_client):
    resp = open_client.post(
        "/v1/extract",
        json={"url": "https://example.com"},
        headers={"X-Open-Token": "wrong-token"},
    )
    assert resp.status_code == 403


def test_open_mode_starts_without_token_and_serves_open(open_env_no_token):
    # REQUIRE_PAYMENT=false with no OPEN_MODE_TOKEN: starts normally, token None.
    settings = load_settings()
    assert settings.require_payment is False
    assert settings.open_mode_token is None


def test_open_mode_no_token_serves_unpaid_post_without_header(open_client_no_token):
    resp = open_client_no_token.post(
        "/v1/extract", json={"url": "https://example.com"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Example"
    assert body["word_count"] == 3


def test_default_still_402(monkeypatch):
    # REQUIRE_PAYMENT unset -> default true -> unpaid POST emits 402.
    monkeypatch.setenv("X402_NETWORK", ARC_MAINNET)
    monkeypatch.setenv("X402_PAY_TO", OWNER_WALLET)
    monkeypatch.delenv("REQUIRE_PAYMENT", raising=False)
    monkeypatch.delenv("OPEN_MODE_TOKEN", raising=False)
    monkeypatch.delenv("CDP_API_KEY_ID", raising=False)
    monkeypatch.delenv("CDP_API_KEY_SECRET", raising=False)
    import app.main as main_mod

    importlib.reload(main_mod)
    from fastapi.testclient import TestClient

    client = TestClient(main_mod.app)
    resp = client.post("/v1/extract", json={"url": "https://example.com"})
    assert resp.status_code == 402
