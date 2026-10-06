"""Unit tests for the extractor — pure functions only, no network, no payment."""

from app.extractor import _extract_with_bs, summarize_text

SAMPLE_HTML = """
<html><head><title>Test Article</title></head>
<body>
<nav>nav junk</nav>
<script>var x = 1;</script>
<article>
<h1>Test Article</h1>
<p>Artificial intelligence agents are changing how software buys software.
The x402 protocol lets agents pay for API calls with stablecoins.</p>
<p>Micropayments under one cent become viable when gas is sponsored by a
facilitator. This unlocks pay-per-call pricing for research tools.</p>
<p>Sellers register a wallet address and a price. Buyers sign an
authorization and retry the request with a payment header.</p>
</article>
<footer>footer junk</footer>
</body></html>
"""


def test_bs_extraction_strips_chrome():
    title, text = _extract_with_bs(SAMPLE_HTML)
    assert title == "Test Article"
    assert "Artificial intelligence agents" in text
    assert "nav junk" not in text
    assert "var x = 1" not in text
    assert "footer junk" not in text


def test_summarize_returns_n_sentences():
    text = (
        "Dogs are loyal companions. "
        "Cats are independent hunters. "
        "Birds can fly long distances. "
        "Fish live underwater their whole lives. "
        "Horses run fast across plains."
    )
    summary = summarize_text(text, n_sentences=2)
    assert len([s for s in summary.split(". ") if s.strip()]) == 2


def test_summarize_short_text_unchanged():
    text = "Only one sentence here."
    assert summarize_text(text, n_sentences=5) == text


def test_summarize_prefers_content_words():
    text = (
        "The x402 payment protocol enables agent micropayments. "
        "Weather is nice today in the city. "
        "Agents use x402 to pay for API calls with USDC. "
        "I had toast for breakfast this morning."
    )
    summary = summarize_text(text, n_sentences=2)
    assert "x402" in summary
