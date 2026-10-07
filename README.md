# Extractr — x402 pay-per-call web content extraction API

POST a URL → get clean readable text + an extractive summary back.
Buyers pay **$0.02 USDC per call** on Base via the [x402 protocol](https://x402.org)
(HTTP 402). No accounts, no API keys — payment is the authentication.

## Endpoints

| Endpoint | Auth | What |
|---|---|---|
| `POST /v1/extract` | x402 paid ($0.02 USDC) | `{url, summary_sentences?, max_chars?}` → `{title, text, summary, word_count, …}` |
| `GET /quote` | free | price, network, payTo |
| `GET /health` | free | liveness |
| `GET /debug` | free | operator config (no secrets) |
| `GET /.well-known/x402` | free | machine-readable service manifest |
| `GET /skill.md`, `/llms.txt` | free | agent-readable docs |

## Quick start (local)

```bash
cd ~/workspace/x402-service
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Testnet mode (Base Sepolia, public facilitator, no keys needed):
X402_NETWORK=eip155:84532 .venv/bin/python -m uvicorn app.main:app --port 8000

# Mainnet mode (real USDC — needs CDP keys, see below):
# X402_NETWORK=eip155:8453 CDP_API_KEY_ID=... CDP_API_KEY_SECRET=... \
#   .venv/bin/python -m uvicorn app.main:app --port 8000

# Arc mainnet mode (real USDC on Circle's Arc, keyless public facilitator):
# X402_NETWORK=eip155:5042 X402_SERVICE_NAME=extractr-arc \
#   .venv/bin/python -m uvicorn app.main:app --port 8000
```

Unpaid call → `402 Payment Required` with a `payment-required` header:

```bash
curl -X POST localhost:8000/v1/extract \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com"}' -i
```

## End-to-end paid test (Base Sepolia, free)

1. Start the server in testnet mode (above).
2. Get a throwaway wallet funded with Sepolia ETH + USDC:
   - Sepolia ETH: https://www.alchemy.com/faucets/base-sepolia (or any Base Sepolia faucet)
   - Sepolia USDC: `0x036CbD53842c5426634E7929541eC2e38FdD67B5` — use a faucet or swap
3. Pay from Node with the official client:
```ts
import { wrapFetchWithPayment } from "x402-fetch";
import { createWalletClient, http, privateKeyToAccount } from "viem";
import { baseSepolia } from "viem/chains";

const account = privateKeyToAccount(process.env.BUYER_KEY as `0x${string}`);
const wallet = createWalletClient({ account, chain: baseSepolia, transport: http() });
const pay = wrapFetchWithPayment(fetch, wallet);
const res = await pay("http://localhost:8000/v1/extract", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ url: "https://example.com", summary_sentences: 3 }),
});
console.log(await res.json());
```
4. Confirm the USDC landed in `X402_PAY_TO` on Base Sepolia
   (https://sepolia.basescan.org).

## Going to mainnet (real money)

1. Create a **free** API key at https://portal.cdp.coinbase.com
   (API Key, not Server Wallet — the facilitator only needs verify/settle auth).
2. Set env:
   ```
   X402_NETWORK=eip155:8453
   CDP_API_KEY_ID=<key id>
   CDP_API_KEY_SECRET=<private key>
   ```
   (`X402_PAY_TO` already defaults to the owner's Base payout wallet;
   override per-environment if needed.)
3. Deploy somewhere with a **public HTTPS URL** (see below) and re-run the
   paid test with real (tiny) USDC.
4. Make **one real settled payment** through the CDP facilitator (even a
   self-buy of $0.02) — that single settlement is what auto-indexes the
   service on agentic.market / x402 Bazaar.

## Deploy options

| Option | Notes |
|---|---|
| **Railway** | `Dockerfile` included; set env vars in dashboard; free tier works |
| **Fly.io** | `fly launch` from the Dockerfile; ~$2/mo for always-on |
| **VPS** (Hetzner $4/mo etc.) | Docker or systemd + Caddy for HTTPS |
| Cloudflare Tunnel | free HTTPS for a home/VPS box without opening ports |

Requirements: public `https://` origin (agents and indexers won't call
`http://`), env vars from `.env.example`, port 8000.

## Listing for discovery (after deploy)

See `BUILD_REPORT.md` §3 for the full listing plan. Short version:

1. **x402scan** — submit base URL at https://x402scan.com/resources/register
   (reads `/.well-known/x402`; works immediately)
2. **agentic.market** — validate at https://agentic.market/validate, then it
   auto-indexes after the first CDP-facilitator settlement (~6h refresh)
3. **x402 Bazaar** — automatic via the discovery extension already embedded
   in the 402 responses, once settling through CDP

## Project layout

```
app/
  main.py       FastAPI app + x402 v2 middleware wiring
  config.py     env-driven settings (wallet = config value, network-aware facilitator)
  cdp_auth.py   CDP facilitator JWT auth (official cdp-sdk)
  extractor.py  fetch + trafilatura extraction + extractive summary
  discovery.py  /.well-known/x402 manifest, skill.md, llms.txt
tests/          extractor unit tests (no network)
Dockerfile      production image
```

## Price rationale

$0.02/call: undercuts typical $0.05–0.10 data APIs, 2–20× the $0.001–0.01
floor most x402 services sit at, and comfortably above the sub-cent
settlement cost on Base. Adjust with `X402_PRICE_USDC` (any `"$X.XX"` string).
