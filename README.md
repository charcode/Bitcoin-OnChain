# Bitcoin On-Chain

Bitcoin On-Chain is a research codebase for estimating BTC/USD from Bitcoin-native activity rather than from a direct exchange feed. The backend connects to a local Bitcoin Knots RPC node, optionally uses Fulcrum for faster historical block retrieval, scans live mempool outputs, reads older blocks, and applies round-number resonance plus stencil-based heuristics to infer a market price from on-chain transaction behavior.

The repository already contains two main analysis modes:

- A live nowcaster based on mempool transaction outputs and RNR scoring.
- A historical stencil estimator that scans older blocks and maps output distributions to round-dollar anchors.

## Current Repository Layout

```text
backend/
  .env
  local.env
  environment.yaml
  show.ps1
  btc_onchain/
    main.py
    config.py
    rpc.py
    models.py
    rnr.py
    state.py
    types.py
    workers.py
    api/
      routes.py
      routes_prices.py
    core/
      app_state.py
      distribution_engine.py
      external_prices.py
      fulcrum_client.py
      mempool_cache.py
      rnr_engine.py
      stencil_price.py
    oracle/
      utxoracle_live.py
frontend/
  src/
  public/
  package.json
  README.md
UTXOracle.py
DEPLOYMENT.md
agents.md
claude.md
gemini.md
dev-protocol.md
todo.md
```

## System Overview

### Data sources

- Bitcoin Knots RPC is the required primary source for mempool and block data.
- Fulcrum is an optional secondary source used to accelerate historical block transaction retrieval.
- External price polling exists in the codebase as an optional comparison layer and should remain clearly separated from the core on-chain estimator.

### Live estimation flow

1. `MempoolCache` continuously refreshes recent outputs from the mempool.
2. `RnrEngine` evaluates candidate USD price levels by converting BTC outputs into implied USD values.
3. The engine scores how strongly those outputs cluster around round-dollar anchors such as `$10`, `$50`, `$100`, `$500`, and larger grids.
4. The best-scoring region becomes the live estimate exposed through the API.

### Historical stencil flow

1. A block range is fetched from Knots RPC, with optional Fulcrum acceleration.
2. Eligible transaction outputs are filtered into a histogram in BTC space.
3. A calibrated stencil is slotted across the histogram to align recurring round-dollar signatures.
4. The best stencil alignment produces an estimated BTC/USD price and per-round-anchor statistics.

## Backend Setup

### Requirements

- Python 3.11
- Conda or Miniconda
- A fully synced Bitcoin Knots node with RPC enabled
- Optional: Fulcrum for faster historical retrieval

### Bitcoin Knots configuration

Minimal `bitcoin.conf`:

```ini
server=1
txindex=1
rpcuser=youruser
rpcpassword=yourpass
rpcallowip=127.0.0.1
rpcport=8332
```

Recommended for research workloads:

```ini
daemon=1
rpcworkqueue=64
rpcthreads=16
```

### Python environment

```powershell
cd backend
conda env create -f environment.yaml
conda activate btc-onchain
```

### Backend environment variables

The backend loads `backend/local.env` first and then `backend/.env`.

Core variables:

```powershell
setx BTC_RPC_URL "http://127.0.0.1:8332"
setx BTC_RPC_USER "youruser"
setx BTC_RPC_PASS "yourpass"
```

Useful tuning variables:

```powershell
setx DECODE_PER_TICK "50"
setx SCAN_INTERVAL "0.75"
setx LOOKBACK_SEC "900"
setx MIN_SAMPLES "500"

setx PRICE_MIN "20000"
setx PRICE_MAX "120000"
setx PRICE_STEP "50"

setx SIGMA "75"
setx EMA_ALPHA "0.25"

setx HIST_SPAN_MULTS "8"
setx HIST_SIGMA_FRAC "0.20"
```

Optional Fulcrum variables:

```powershell
setx FULCRUM_ENABLED "true"
setx FULCRUM_HOST "127.0.0.1"
setx FULCRUM_PORT "50002"
setx FULCRUM_SSL "true"
setx FULCRUM_SSL_VERIFY "false"
setx FULCRUM_TIMEOUT "30"
```

Optional external comparison price polling:

```powershell
setx EXT_PRICE_ENABLED "false"
setx EXTERNAL_PRICE_SOURCES "coindesk,binance,kraken,coinbase"
```

## Running The Project

### Backend

```powershell
cd backend
conda activate btc-onchain
uvicorn btc_onchain.main:app --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend defaults to Vite and React 19. Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

### Docker Compose

The repository includes service images for the local operating stack:

- `bitcoin-on-chain/datum-gateway:local` runs the existing Linux Datum gateway build from `F:/bitcoin/datum_gateway/build`.
- `bitcoin-on-chain/fulcrum:1.12.0` downloads and runs the Fulcrum Linux release in a container.
- `bitcoin-on-chain/backend:local` runs `btc_onchain.main:app` with Uvicorn.
- `bitcoin-on-chain/frontend:local` builds the Vite dashboard and serves it with `vite preview`.

Create a Docker environment file from `.env.docker.example`, then run:

```powershell
copy .env.docker.example .env.docker
docker compose --env-file .env.docker --profile monitoring --profile mining up --build
```

Use only `--profile monitoring` when you want Fulcrum, backend, and frontend without the Datum mining gateway.

Important runtime notes:

- Docker cannot run the Windows `Fulcrum.exe` in a normal Linux container. The Fulcrum image uses the matching Linux release and mounts your existing `fulcrum.conf`.
- Any paths inside `fulcrum.conf` must be valid inside the container. Use `/data/fulcrum` for the mounted Fulcrum data directory.
- `BTC_RPC_URL` should normally point at `http://host.docker.internal:8332` so the backend and Fulcrum container can reach the host Bitcoin Knots node.

## API Surface

### Health and live estimator

- `GET /health`
- `GET /price/now`
- `GET /rnr/curve`
- `GET /debug/candidates`
- `GET /debug/histogram`
- `GET /debug/heatmap`
- `GET /debug/distribution`

### Historical block and stencil endpoints

- `GET /debug/blocks`
- `GET /debug/stencil_price`
- `GET /debug/blocks_csv`
- `GET /debug/mempool_csv`

### Optional external comparison endpoints

- `GET /external/price/sources`
- `GET /external/price/now`
- `GET /external/price/history`
- `GET /price/compare`

## Engineering Direction

This project should be treated as a research system with production-style discipline:

- Keep Bitcoin node access behind a narrow RPC client boundary.
- Keep feature extraction separate from inference logic.
- Keep historical block analysis separate from live mempool analysis.
- Keep optional external price polling isolated so it cannot contaminate the core estimator.
- Prefer deterministic, testable pure functions for histogram building, binning, resonance scoring, and stencil alignment.
- Record assumptions about round-dollar anchors, filters, and calibration constants in Markdown next to the code changes that introduce them.

## Recommended Module Boundaries

- `rpc.py`: transport and RPC method wrappers only
- `core/mempool_cache.py`: mempool ingestion and retention policy only
- `rnr.py` and `core/rnr_engine.py`: resonance computation only
- `core/stencil_price.py`: historical stencil estimator only
- `core/distribution_engine.py`: histogram and distribution diagnostics only
- `api/`: request validation and response shaping only
- `models.py`: shared response and domain schemas only

Avoid pushing business logic into FastAPI routes, background loop wiring, or ad hoc scripts.

## Testing Priorities

### Performance update — 2026-10-13

Live ingestion now decodes each recent mempool transaction once. Seen IDs are retained while the transaction is in the mempool or its observed outputs remain in the rolling window, so repeated scans and short disappear/reappear episodes do not create duplicate samples. Old mempool entries outside `LOOKBACK_SEC` are not counted as fresh arrivals on restart. Failed decode attempts count toward `DECODE_PER_TICK` and can be retried on the next poll.

Historical stencil analysis uses a shared, bounded cache of compact eligible transaction inputs and output amounts, keyed by the node's actual block hash. It fetches a cold block with one `getblock(hash, 2)` RPC; Fulcrum is a fallback and incomplete responses are rejected. Window-dependent spending exclusions are reapplied for each requested range. The background result is refreshed when the chain tip hash or selected range changes, including reorganizations at the same height. The estimator's filters, histogram calibration, stencil scoring, and round-USD anchors are unchanged. Removing duplicate live observations can change the experimental nowcast.

Diagnostic USD histograms use NumPy window masks with the same inclusive boundaries and counts; weighted sums may differ only by floating-point summation rounding.

New tuning variables: `STENCIL_CACHE_BLOCKS=288` (compact block LRU capacity), `STENCIL_LOOKBACK_BLOCKS=144` (background range), and `STENCIL_INTERVAL_SEC=180` (tip check cadence). Cache entries do not expire by time: each requested height is validated against its current block hash. A cold startup still needs one fetch per uncached block; later rolling windows fetch only new or reorganized blocks.

Run deterministic backend tests with the backend dependencies installed:

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -m unittest discover -s backend/tests -v
```

Alienware's live Compose stack is `C:\BitcoinLANPortal\docker-compose.yml`, service `resonance-backend`; it uses the source checkout at `D:\charbel\Documents\AiiQ\github\bitcoin_on_chain`. Deploy this service independently to preserve the other Bitcoin/mining applications. The 2026-10-13 performance image is layered on the previous backend image to retain its dependency versions; source changes also apply to future regular backend builds. Keep the previous image and source backup for rollback.

The backend unit suite now covers live ingestion, historical caching/filtering, histogram equivalence, and cached stencil responses. Remaining test priorities include:

1. Deterministic unit tests for round-number resonance scoring on synthetic outputs.
2. Unit tests for stencil alignment and neighbor-slide interpolation.
3. Tests for transaction filtering rules in the historical block pipeline.
4. Tests for mempool retention, pruning, and distribution bucketing.
5. API tests covering invalid block ranges, empty samples, and timeout/error behavior.

## Documentation For AI Agents

The root documentation set is intended to initialize agent sessions consistently:

- `agents.md`: canonical project context and working rules
- `architecture.md`: current implementation architecture and runtime flow
- `dev-protocol.md`: engineering protocol for design, testing, modularity, and review
- `todo.md`: current work queue and research backlog
- `claude.md`: bootstrap instructions for Claude-based agents
- `gemini.md`: bootstrap instructions for Gemini-based agents

All agents should begin by reading `agents.md`, then `architecture.md`, then recursively follow the linked Markdown files before making changes.

## Known Documentation Corrections

The previous root README had drift in a few areas:

- It described an older target structure instead of the actual backend modules.
- It mixed aspirational behavior with implemented behavior.
- It did not document the stencil estimator and Fulcrum integration clearly enough.

This README now reflects the current repository more closely, but it should continue to be updated whenever the architecture changes.

## Roadmap

- Add a real automated test suite for backend core logic.
- Separate calibration constants from executable stencil logic.
- Add reproducible fixtures for old blocks and mempool snapshots.
- Define benchmark datasets for evaluating estimator drift versus external references.
- Decide whether external price polling remains a debug aid or becomes a formal evaluation subsystem.

## Credits

This repository draws clear inspiration from UTXOracle and related round-number resonance ideas, while adapting them to a live Bitcoin mempool and historical block workflow.

## License

No project license is currently declared in the repository.


## Estimation evaluation and shadow refinement — 2026-10-18

The primary live estimator remains `legacy`; `/price/evaluation` exposes a separate `raw-anchor-kde-v1-shadow` candidate, its status, and actual exchange comparison errors. No exchange quote enters either inference path. `/price/compare` now accepts the typed response and returns null errors when a benchmark/model is unavailable, stale, or more than 45 seconds apart.

The shadow model uses the strongest coarse on-chain resonance point only to select a local ±4% logarithmic region. It converts exact BTC outputs into implied prices for fixed round-USD anchors `[5,10,15,20,25,30,40,50,100,150,200,300,500,1000]`. Exact 1,000-satoshi multiples are excluded as round-BTC artifacts; genuine coincident payments may also be lost. A weighted log-price KDE at widths .0015/.003/.006 is evaluated on 161 grid points; nearby raw implied prices yield a weighted median. These are experimental design constants, not exchange-fitted calibration. No stencil coefficients or fixed dollar offsets have been changed.

It requires at least 30 effective output weights and three denominations, rejects boundary modes, near-equivalent distinct modes, and under-10% local support among matched implied prices. Full-sample support is reported separately. Effective output counts do not establish independent transaction observations. It evaluates at most every ten seconds on the existing observation batch, with no second RPC ingestion loop. An exception cannot interrupt publication of the legacy estimate.

The cyan band is the envelope of contiguous >=80%-of-peak support regions across the three kernel widths. It is MODEL SENSITIVITY, not a calibrated confidence interval, forecast interval, or promised error bound. The chart shows actual exchange error separately. The deployment restores the default minimum 500 outputs (the earlier runtime override was 5), avoiding startup estimates from a tiny sample. The legacy low-sample path now holds its last price/timestamp and reports insufficient data instead of multiplying it toward zero.

Exchange comparison uses Kraken, Coinbase and Bitstamp BTC/USD last-trade quotes only. Quote retrieval expires at 90 seconds; known market timestamps expire at 120 seconds, and model computations expire at 30 seconds. Retrieval time is not necessarily trade time. Failed/stale quotes are excluded. Signed error means model minus the fresh-source USD median. These thresholds describe freshness eligibility, not an estimation accuracy guarantee.

Evaluation samples run every 30 seconds and deduplicate reference timestamps. The API reports paired 24-hour bias, MAE, MAPE, 95th-percentile absolute percentage error and measured band coverage using the same reference timestamps for both models. Valid comparisons, model timestamps/versions/quality and individual quote histories persist for 14 days in SQLite. Early paired observations are NOT prospective validation. No model promotion is automated.

Runtime overlay: `C:\BitcoinLANPortal\docker-compose.price-shadow.yml`, alongside the existing base Compose file. A new `resonance_price_evaluation` named volume holds `/data/evaluation.sqlite`. Only the two Resonance services are recreated. Rollback images are tagged `before-price-shadow-20261018`; source/config backups remain in `C:\BitcoinNode\performance\resonance-improve-20261018`. Retain the evaluation volume on rollback. Restore only scoped files, never overwrite environment/other dirty work.

UI repairs migrate Tailwind directives to v4 import syntax, constrain the hero size, remove arbitrary live/historical blending and fake confidence corridors, and place a visible evaluation panel above the legacy display. Exchange prices are labeled comparison-only.


## Fresh-clone reproduction

Use [REPRODUCE.md](REPRODUCE.md) and `compose.repro.yml` for source builds with locked Python/frontend dependencies. This does not depend on private Alienware image layers.
