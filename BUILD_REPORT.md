# BUILD REPORT — Extractr x402 pay-per-call service

**Date:** 2026-10-06
**Status:** scaffolded + smoke-tested. NOT deployed, NOT listed. Nothing spent.
**Code:** `~/workspace/x402-service/` (app, tests, Dockerfile, README)

---

## 1. Research findings (x402 protocol, verified 2026-10-06)

- **Protocol:** x402 v2 (now under the Linux Foundation's x402 Foundation;
  Coinbase contributed it). Flow: buyer calls endpoint → server returns
  `402 Payment Required` + base64 `payment-required` header → buyer signs an
  EIP-3009 `transferWithAuthorization` → retries with payment header →
  **facilitator** verifies + settles on-chain → server returns the resource +
  `payment-response` header.
- **Seller SDK:** official Python package `x402[fastapi,evm]` (v2.25.0, current).
  FastAPI middleware: `fastapi_payment_middleware(routes, server)` with
  `PaymentOption(scheme="exact", price="$0.02", network="eip155:8453", payTo=…)`.
- **Critical gotcha (verified live):** the public `x402.org/facilitator`
  settles **testnets only** (Base Sepolia `eip155:84532`, Solana devnet…).
  **Base mainnet requires the Coinbase CDP facilitator**
  (`https://api.cdp.coinbase.com/platform/v2/x402`) with per-request Ed25519
  JWT auth from a free CDP API key. The scaffold handles both modes
  automatically (see §2).
- **Ecosystem (self-reported by Coinbase, not independently verified):**
  ~75M txns / $24M volume / 94K buyers / 22K sellers per 30d (July 2026
  snapshot). Only ~14% of indexed services actually return data when paid
  (ScoutScore) — a reliability gap a working service can exploit.
- **Discovery:** no signup anywhere. agentic.market (Coinbase-operated)
  auto-indexes a service after its **first settled payment through the CDP
  facilitator** (~6h refresh); x402scan.com takes a manual URL submission and
  reads `/.well-known/x402`; x402 Bazaar reads the discovery extension
  embedded in 402 responses.
- **Pricing landscape:** $0.0001–$1,000/call across the catalog; most utility
  endpoints sit at $0.001–$0.10.

## 2. What was built

**Service: Extractr** — `POST /v1/extract` takes a URL, returns clean readable
text + extractive summary + metadata. Chosen because: (a) every research
agent needs exactly this, constantly; (b) it works with zero API keys
(trafilatura extraction + TF-based summarization, deterministic); (c) the
"Real World Data / research" category is one of the busiest in the x402
wiki. A clearly better alternative did not emerge from research.

- `app/main.py` — FastAPI + x402 v2 middleware, paid route + free
  `/health /quote /debug /.well-known/x402 /skill.md /llms.txt`
- `app/config.py` — **payout wallet is a config value** (`X402_PAY_TO`,
  default `0x097f9685D1e0752bF8B02d61E5Ce9be7eA0FBA7F` — owner's Base payout
  wallet, set per his 2026-10-06 decision). Network-aware facilitator
  selection: mainnet→CDP (requires keys, fails fast with instructions if
  missing), testnet→public facilitator (keyless).
- `app/cdp_auth.py` — CDP JWT auth via the **official** `cdp-sdk`
  (`generate_jwt`), per-operation fresh tokens (verify/settle/supported).
- `app/extractor.py` — httpx fetch (timeout, 2MB cap, UA) → trafilatura
  (BeautifulSoup fallback) → extractive summary. No model/API keys.
- `app/discovery.py` — Bazaar discovery extension embedded in 402s
  (input schema, output example, description) + manifest/skill/llms.txt.
- `tests/` — 4 unit tests, passing. `Dockerfile` — production image.
- Verified live: boots; unpaid `POST /v1/extract` → `402` with correct
  challenge (exact/$0.02/Base Sepolia/payTo=owner wallet); free endpoints OK.
  (Sandbox proxy quirk with bracketed IPv6 `no_proxy` worked around in
  `main.py`; not an issue on normal hosts.)

**Recommended price: $0.02 USDC/call** — undercuts typical data APIs,
well above sub-cent Base settlement cost. One-line change via
`X402_PRICE_USDC`.

## 3. Listing plan (after deploy — owner approves separately)

1. Deploy to a public HTTPS URL (Railway / Fly.io / VPS — see README).
2. **x402scan** — https://x402scan.com/resources/register → submit base URL
   (reads `/.well-known/x402`). Immediate.
3. **agentic.market** — https://agentic.market/validate → validate, then make
   **one real $0.02 self-buy** through the CDP facilitator; auto-indexed
   within ~6h. This is also the Bazaar listing trigger.
4. Optional: announce in x402/agent dev communities (e.g. x402 Discord,
   relevant subreddits) — distribution is the actual bottleneck, not tech.

## 4. Owner decisions needed (nothing proceeds without these)

1. **CDP API keys** — create free key at https://portal.cdp.coinbase.com,
   set `CDP_API_KEY_ID` / `CDP_API_KEY_SECRET`. **This is the single blocker
   for mainnet.** (Testnet works today with zero keys.)
2. **Deployment target** — Railway (easiest), Fly.io, or VPS. Needs his
   account/click; I can do Railway/Fly config once he picks.
3. **Listing** — approve after deploy: x402scan submission + one $0.02
   self-buy to trigger agentic.market/Bazaar indexing.
4. **Price** — $0.02 recommended; say the word to change.
5. **Wallet** — currently defaults to `0x097f9685D1e0752bF8B02d61E5Ce9be7eA0FBA7F`
   (his OpenTask payout wallet, Base). Override with `X402_PAY_TO` if he
   wants earnings separated.

## 5. Honest caveats

- x402 volume is real but early; most "services" are experiments and buyer
  traffic is thin. This is a lottery ticket with good odds *relative* to
  other agent-earning channels, not a salary.
- The 14%-actually-work stat is our edge: a service that reliably returns
  data on every paid call stands out.
- CDP had a `/verify` regression mid-2026 (issue #2832); if mainnet paid
  calls fail at verify despite correct setup, check x402-foundation/x402
  issues before debugging our code.
- Costs to run: ~$0–5/mo hosting; facilitator takes no cut on Base USDC
  (Coinbase currently subsidizes); only Base gas per settlement (cents).
