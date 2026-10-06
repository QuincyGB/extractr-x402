"""URL fetching + clean-text extraction + extractive summarization.

No API keys needed: trafilatura for readability extraction, with a
BeautifulSoup fallback, and a deterministic TF-based extractive summary.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

try:
    import trafilatura

    _HAS_TRAFILATURA = True
except ImportError:  # pragma: no cover
    _HAS_TRAFILATURA = False

_BROWSER_UA = (
    "Mozilla/5.0 (compatible; Extractr/1.0; +https://github.com/extractr) "
    "AppleWebKit/537.36"
)

_STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been
    before being below between both but by can did do does doing down during each
    few for from further had has have having he her here hers herself him himself
    his how i if in into is it its itself just like me more most my myself no nor
    not now of off on once only or other ought our ours ourselves out over own same
    she should so some such than that the their theirs them themselves then there
    these they this those through to too under until up very was we were what when
    where which while who whom why with would you your yours yourself yourselves
    also one two new first may many made use used using""".split()
)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
_WORD = re.compile(r"[a-z]{3,}")


@dataclass
class ExtractedPage:
    url: str
    final_url: str
    title: str
    text: str
    word_count: int
    char_count: int
    summary: str
    summary_sentences: int
    truncated: bool


class FetchError(RuntimeError):
    pass


def _tokenize_sentences(text: str) -> list[str]:
    sents = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    return [s for s in sents if len(s) > 20]


def summarize_text(text: str, n_sentences: int = 5) -> str:
    """Extractive summary: rank sentences by normalized term frequency.

    Deterministic, no model needed. Good enough for a paid utility endpoint;
    agents that want abstractive summaries can pipe the returned text onward.
    """
    sentences = _tokenize_sentences(text)
    if len(sentences) <= n_sentences:
        return " ".join(sentences)

    freq: dict[str, int] = {}
    for sent in sentences:
        for w in _WORD.findall(sent.lower()):
            if w not in _STOPWORDS:
                freq[w] = freq.get(w, 0) + 1
    if not freq:
        return " ".join(sentences[:n_sentences])

    max_f = max(freq.values())
    scored: list[tuple[float, int, str]] = []
    for i, sent in enumerate(sentences):
        words = [w for w in _WORD.findall(sent.lower()) if w not in _STOPWORDS]
        if not words:
            continue
        score = sum(freq[w] / max_f for w in words) / math.sqrt(len(words))
        # slight preference for earlier sentences (lede bias)
        score *= 1.0 / (1.0 + 0.05 * i)
        scored.append((score, i, sent))

    top = sorted(scored, reverse=True)[:n_sentences]
    top.sort(key=lambda t: t[1])
    return " ".join(s for _, _, s in top)


def _extract_with_trafilatura(html: str, url: str) -> tuple[str, str]:
    """Returns (title, text). Raises on failure so caller can fall back."""
    downloaded = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        output_format="txt",
    )
    if not downloaded or len(downloaded.strip()) < 200:
        raise ValueError("trafilatura returned too little text")
    meta = trafilatura.extract_metadata(html, default_url=url)
    title = (meta.title if meta and meta.title else "") or ""
    return title, downloaded.strip()


def _extract_with_bs(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = "\n".join(ln for ln in lines if len(ln) > 40)
    return title, cleaned


async def fetch_and_extract(
    url: str,
    *,
    timeout_s: float,
    max_bytes: int,
    summary_sentences: int,
    max_chars: int | None = None,
) -> ExtractedPage:
    if not url.startswith(("http://", "https://")):
        raise FetchError("url must start with http:// or https://")

    async with httpx.AsyncClient(
        timeout=timeout_s,
        follow_redirects=True,
        headers={"User-Agent": _BROWSER_UA, "Accept": "text/html,*/*"},
    ) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise FetchError(f"fetch failed: {e}") from e
        content = resp.content[:max_bytes]
        final_url = str(resp.url)

    ctype = resp.headers.get("content-type", "")
    if "html" not in ctype and "text" not in ctype and ctype:
        raise FetchError(f"unsupported content-type: {ctype}")

    html = content.decode("utf-8", errors="replace")

    title, text = "", ""
    if _HAS_TRAFILATURA:
        try:
            title, text = _extract_with_trafilatura(html, final_url)
        except Exception:
            title, text = _extract_with_bs(html)
    else:
        title, text = _extract_with_bs(html)

    if len(text.strip()) < 100:
        raise FetchError("no readable content extracted from page")

    truncated = False
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0]
        truncated = True

    summary = summarize_text(text, n_sentences=summary_sentences)
    words = len(text.split())
    return ExtractedPage(
        url=url,
        final_url=final_url,
        title=title,
        text=text,
        word_count=words,
        char_count=len(text),
        summary=summary,
        summary_sentences=summary_sentences,
        truncated=truncated,
    )
