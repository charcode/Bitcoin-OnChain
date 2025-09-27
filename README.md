# BTC On-Chain - Live RNR Nowcaster

Estimate Bitcoin's spot price from mempool outputs using a Round-Number Resonance (RNR) signal.

- Backend: Python 3.10+, FastAPI (Uvicorn)
- Frontend: React + Vite (TypeScript)

Idea: Convert each mempool output (BTC) to USD at candidate prices on a grid. Outputs tend to cluster near round USD buckets when the price guess is right. The sharpest resonance (peak height, prominence, and narrow width) is the nowcast; confidence reflects peak quality.

---

## Repo layout

```
.
- backend/                  # Python package: btc_onchain
  - btc_onchain/
    - main.py               # FastAPI app (import path: btc_onchain.main:app)
    - config.py             # env vars and defaults
    - rpc.py                # Rpc class (final; keep as-is)
    - mempool.py            # mempool scanner and rolling cache
    - rnr.py                # RNR search and histogram
    - state.py              # AppState and RnrEngine
- frontend/                 # React + Vite dashboard (TypeScript)
  - index.html
  - src/
    - main.tsx, App.tsx
    - components/           # CurveChart, DebugBar, PriceCards, CandidatesPanel
    - lib/                  # api.ts, types.ts
```

---

## 1) Checkout

Your remote is configured as:
```bash
git remote -v
origin  github-charcode:charcode/Bitcoin-OnChain.git (fetch)
origin  github-charcode:charcode/Bitcoin-OnChain.git (push)
```

Clone (SSH alias):
```bash
git clone github-charcode:charcode/Bitcoin-OnChain.git
cd Bitcoin-OnChain
```

Or HTTPS:
```bash
git clone https://github.com/charcode/Bitcoin-OnChain.git
cd Bitcoin-OnChain
```

---

## 2) Prerequisites

- Bitcoin Core with RPC (server=1, rpcuser=..., rpcpassword=...)
- Python 3.10+ (3.11 recommended)
- Node.js 18+ (20 LTS recommended) and npm/pnpm/yarn

---

## 3) Backend (FastAPI)

### Install
```bash
cd backend
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Minimal deps:
pip install "fastapi>=0.111" "uvicorn[standard]>=0.30" "httpx>=0.27" "pydantic>=2.7"
```

(Optional) create backend/requirements.txt with the same packages and use:
```bash
pip install -r requirements.txt
```

### Configure

Create backend/.env (example values):
```bash
# Bitcoin Core RPC
BTC_RPC_URL=http://127.0.0.1:8332
BTC_RPC_USER=youruser
BTC_RPC_PASS=yourpass

# Mempool scanning
LOOKBACK_SEC=900
POLL_INTERVAL=5
SCAN_INTERVAL=10
DECODE_PER_TICK=400
MIN_SAMPLES=50

# RNR grid (USD)
PRICE_MIN=30000
PRICE_MAX=120000
PRICE_STEP=50

# Kernel/smoothing
# IMPORTANT: SIGMA is a FIXED USD width (not a fraction of price)
SIGMA=50
EMA_ALPHA=0.25

# Optional multi-grids / histogram span (used internally)
RNR_GRIDS=10,25,50,100,250,500,1000,2000,5000,10000
HIST_SPAN_MULTS=8
```

Tuning notes:
- Lower SIGMA (for example, 25) -> sharper peaks; higher (75-100) -> smoother curve.
- Ensure PRICE_STEP and SIGMA are in the same ballpark (for example, both ~ 50 USD).

### Run (dev)
```bash
cd backend
# venv active
uvicorn btc_onchain.main:app --reload --port 8000
```

### API (quick reference)

| Route                | Method | Description |
|---------------------|--------|-------------|
| /health             | GET    | Liveness ping |
| /price/now          | GET    | { t, price, confidence, curvature, samples_used } |
| /rnr/curve          | GET    | { t, points: [{p, s}] } normalized grid (z-scores) |
| /debug/candidates   | GET    | { total_outputs_cached, usable } |
| /debug/histogram    | GET    | Counts per round-USD bucket; query: price, step |

Examples:
```bash
curl http://127.0.0.1:8000/price/now
curl "http://127.0.0.1:8000/debug/histogram?price=61234&step=50"
```

---

## 4) Frontend (Vite + React)

### Install
```bash
cd frontend
npm install
```

Create frontend/.env:
```bash
VITE_API_URL=http://127.0.0.1:8000
```

### Run (dev)
```bash
npm run dev
# usually http://127.0.0.1:5173
```

The UI polls:
- /price/now (estimate and confidence)
- /rnr/curve (chart)
- /debug/candidates (cache stats)
- /health (liveness)
- /debug/histogram (round-USD bucket histogram)

### Build (prod)
```bash
npm run build     # outputs to frontend/dist
npm run preview   # optional local preview of the built app
```

Serve dist/ behind a static server; reverse-proxy / (frontend) and /api (or your chosen path) to the backend.
Ensure CORS in the backend includes your frontend origin.

---

## 5) Tuning and Troubleshooting

Symptoms: price glued near PRICE_MIN (~30000) and confidence ~ 0
Fixes to try:
- Curve too flat -> decrease SIGMA (25-40) or increase PRICE_STEP (25 -> 50).
- Not enough data -> increase LOOKBACK_SEC or DECODE_PER_TICK; verify mempool activity.
- Boundary bias -> widen PRICE_MIN/PRICE_MAX.
- Inspect /debug/histogram around the best price:
  - Clear peaks at round buckets -> good resonance
  - Flat histogram -> gather more data or retune SIGMA/PRICE_STEP.

Endpoint sanity checks:
```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/debug/candidates
curl http://127.0.0.1:8000/rnr/curve
```

Windows / WSL tip:
If Core runs on Windows and backend in WSL, set BTC_RPC_URL to the Windows host or LAN IP and allow RPC from the WSL subnet.

---

## 6) Production

Run Uvicorn behind a reverse proxy (TLS, static files, caching):
```bash
uvicorn btc_onchain.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Serve the built frontend (frontend/dist) via Nginx/Caddy/Traefik and proxy API to the backend.
Update backend CORS to include the production frontend origin.

---

## 7) Optional Makefile

```Makefile
.PHONY: be fe run dev

be:
	cd backend && python -m venv .venv && . .venv/bin/activate && 	pip install -r requirements.txt || pip install fastapi "uvicorn[standard]" httpx pydantic

fe:
	cd frontend && npm install

run:
	cd backend && . .venv/bin/activate && uvicorn btc_onchain.main:app --reload --port 8000

dev:
	( cd backend && . .venv/bin/activate && uvicorn btc_onchain.main:app --reload --port 8000 ) & 	( cd frontend && npm run dev )
```

---

## 8) Contributing

- Keep the Rpc class intact (final).
- Prefer small, testable functions in btc_onchain/.
- Frontend fetchers and types live in frontend/src/lib/.

---

## 9) License

TBD.
