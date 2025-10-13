# btc-onchain — Live RNR Nowcaster

Estimate the **BTC/USD price** *purely from on-chain and mempool activity* by detecting **Round-Number Resonance (RNR)** — clustering of transaction output values around round-dollar amounts across multiple grid sizes (e.g., $50, $100, $500).  
No external price feed is used.

---

## Overview

This project connects directly to a local Bitcoin node and continuously scans the mempool. It converts transaction outputs to USD using candidate price levels, detects resonance at round-number anchors, and exposes the results over a FastAPI backend with a React/Vite frontend.

### Processing pipeline

- **Bitcoin node RPC** ?  
- **MempoolCache** (rolling outputs window) ?  
- **RnrEngine** (multi-grid resonance computation, baseline removal, peak detection) ?  
- **FastAPI API** ?  
- **React/Vite frontend dashboard**

---

## Features

- **Live on-chain only estimation** — no external price feeds.
- **Multi-grid RNR scoring** across different round-dollar anchors.
- **Robust baseline removal & sharpness-based confidence**.
- **Diagnostics**: resonance curve & USD histograms.

---

## Repository layout

```
backend/
  btc_onchain/
    __init__.py
    main.py
    config.py
    models.py
    rpc.py                  # KEEP THIS CLASS
    rnr.py                  # rnr_search(), histogram utilities
    api/
      __init__.py
      routes.py             # /price/now, /rnr/curve, /debug/candidates, /debug/histogram, /debug/distribution, /health
    core/
      __init__.py
      app_state.py          # wires Rpc, MempoolCache, RnrEngine; runs loops
      mempool_cache.py      # rolling outputs cache (BTC values, weights)
      rnr_engine.py         # runs rnr_search in a thread; stores latest results & hist cache
frontend/
  ... (React/Vite app)
show.ps1                    # dumps backend files + README.md + environment.yml
environment.yml             # Anaconda env spec
```

---

## Requirements & Installation (Windows + Anaconda)

### Prerequisites

- [Anaconda/Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- [Node.js LTS](https://nodejs.org)
- [Bitcoin node](https://bitcoinknots.org) fully synced, with RPC enabled.

Minimal `bitcoin.conf`:

```ini
server=1
rpcuser=youruser
rpcpassword=yourpass
rpcallowip=127.0.0.1
rpcport=8332
```

### Backend setup

```powershell
cd backend
conda env create -f environment.yml
conda activate btc-onchain
```

Example `environment.yml`:

```yaml
name: btc-onchain
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - uvicorn
  - fastapi
  - httpx
  - pydantic
  - numpy
  - pip
  - pip:
      - python-dotenv
```

### Environment variables

Set these in PowerShell:

```powershell
setx BTC_RPC_URL  "http://127.0.0.1:8332"
setx BTC_RPC_USER "youruser"
setx BTC_RPC_PASS "yourpass"
# Optional tuning:
setx PRICE_MIN "80000"
setx PRICE_MAX "140000"
setx PRICE_STEP "50"
setx SIGMA "75"
setx EMA_ALPHA "0.25"
setx HIST_SPAN_MULTS "8"
setx HIST_SIGMA_FRAC "0.20"
setx DECODE_PER_TICK "50"
setx LOOKBACK_SEC "900"
```

*(Restart terminal to apply `setx` values.)*

---

## Running

### Backend

```powershell
cd backend
conda activate btc-onchain
uvicorn --host 127.0.0.1 --port 8000 btc_onchain.main:app
```

Endpoints:

- `GET /health`
- `GET /price/now` ? `{ t, price, confidence, curvature, samples_used }`
- `GET /rnr/curve` ? `{ t, points: [{p, s}, ...] }`
- `GET /debug/candidates` ? `{ total_outputs_cached, usable }`
- `GET /debug/histogram?grid=100&span=8` ? histogram bins near round-dollar anchors.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

---

## Configuration

Environment variables (see `config.py`):

- **RPC**: `BTC_RPC_URL`, `BTC_RPC_USER`, `BTC_RPC_PASS`
- **Scanning**:
  - `DECODE_PER_TICK` (default 50): outputs decoded per tick.
  - `LOOKBACK_SEC` (default 900): rolling window.
  - `SCAN_INTERVAL` (default 2s).
- **Price grid**:
  - `PRICE_MIN`, `PRICE_MAX`, `PRICE_STEP`.
- **RNR kernel**:
  - `SIGMA` (default 75).
  - `RNR_GRIDS` (default `[10,25,50,100,250,500,1000,2000,5000,10000]`).
  - `EMA_ALPHA` (default 0.25).
- **Histograms**:
  - `HIST_SPAN_MULTS` (default 8).
  - `HIST_SIGMA_FRAC` (default 0.20).

---

## Algorithm

1. **Scoring**: For candidate price `p`, convert outputs `v_btc` to USD, compute Gaussian kernel score at nearest round-dollar anchors for each grid, scale by `1/sqrt(g)`, sum.
2. **Baseline removal**: median + slow EMA baseline, subtract ? resonance curve.
3. **Best price**: `argmax` resonance.
4. **Confidence**: peak sharpness (discrete curvature) × peak height.
5. **Histogram**: bins around anchors near estimate.

---

## Frontend UI

- **Price cards** summarising nowcaster vs stencil confidence.
- **Resonance curve** with live RNR scores.
- **Historical heatmap** overlay with zoomable mempool buckets.
- **Transaction size distribution** with linear/log/sqrt scale options and round-USD overlays.
- **Control overlay** for grids, heatmap cadence, distribution bins, scale, anchors, and block lookback.

All panels update automatically; no tab switching required.

---

## Troubleshooting

---

## Credits

This project draws significant inspiration from UTXOracle by Simple Steve:

- UTXOracle live site: https://utxo.live/
- Author (X/Twitter): @SteveSimple
- This project author (X/Twitter): @charbel_g

Thank you to Simple Steve for his excellent work on UTXOracle. UTXOracle focuses on providing a historical lookback view (estimating price for a chosen date in the past). This project’s Nowcaster adapts similar round‑number resonance ideas to the present by applying them to the current mempool, aiming to infer a live BTC/USD estimate from on‑chain activity alone.

---

## Get Started (Clone)

Clone via SSH and jump in:

```
git clone git@github.com:charcode/Bitcoin-OnChain.git
cd Bitcoin-OnChain
```

For local dev, Docker, and environment variables, see DEPLOYMENT.md.

- **Price stuck at lower bound**: widen `[PRICE_MIN, PRICE_MAX]`; check `SIGMA`.
- **Confidence ~0**: increase lookback or decode rate, adjust `SIGMA`.
- **Empty candidates**: check RPC connectivity and `bitcoin.conf`.

---

## Logging & Dev loop

- Logs show mempool scan counts & resonance timings.
- Heavy CPU tasks run in `asyncio.to_thread`.

---

## Export helper (PowerShell)

`show.ps1` dumps backend sources + README + environment.yml:

```powershell
# show.ps1 — dump backend sources + env + README
$ErrorActionPreference = 'Stop'
$root   = $PSScriptRoot
$src    = Join-Path $root 'btc_onchain'
if (-not (Test-Path $src)) { Write-Error "btc_onchain/ not found"; exit 1 }

$exclude = @('__pycache__', '.venv', 'venv', '.pytest_cache', '.mypy_cache')
$excludeRx = [regex]('\(' + ($exclude -join '|').Replace('.', '\.') + ')(\|$)')

$py = Get-ChildItem -Path $src -Recurse -File -Include *.py |
      Where-Object { $_.FullName -notmatch $excludeRx } |
      Sort-Object FullName

$extra = @(
  (Join-Path $root 'environment.yml'),
  (Join-Path $root 'README.md')
) | Where-Object { Test-Path $_ }

$files = @($py) + @($extra)

foreach ($f in $files) {
  $rel = $f.FullName.Replace("$root", '')
  "=== $rel ==="
  ""
  Get-Content -Path $f.FullName -Raw
  ""
}
```

Usage:

```powershell
cd backend
.\show.ps1 > dump.txt
```

---

## Security & Notes

- Research/visualization only, **not trading advice**.
- Requires fully synced Bitcoin Core with RPC.
- In-memory cache, no persistence.

---

## Roadmap

- Adaptive `SIGMA` & grid tuning.
- `PRICE_HINT` support.
- Persist warm-start ring buffer.
- UI: multi-grid histograms, decode rate monitoring.

---

## License

*(Add your preferred license here, e.g. MIT or Apache-2.0)*

---


