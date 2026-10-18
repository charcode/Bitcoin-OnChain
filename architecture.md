# Architecture

This document summarizes the current project architecture as implemented in the repository. It is intended for humans and AI agents who need a fast but accurate understanding of the system before making changes.

## Purpose

Bitcoin On-Chain is a research system for estimating BTC/USD from Bitcoin-native activity rather than from direct exchange feeds.

The codebase currently supports two estimator modes:

- A live mempool-based nowcaster.
- A historical block-based stencil estimator.

The project also includes diagnostic APIs and a frontend dashboard for inspecting the signals behind those estimates.

## High-Level System

The system is split into two main applications:

- A Python backend built on FastAPI.
- A React and Vite frontend dashboard.

The backend connects to:

- A local Bitcoin Knots node over JSON-RPC.
- An optional Fulcrum server for faster historical transaction retrieval.
- Optional public exchange APIs for comparison-only external prices.

## Backend Entry Point

The backend starts in `backend/btc_onchain/main.py`.

At startup it:

1. Loads runtime configuration from `backend/btc_onchain/config.py`.
2. Creates the Knots RPC client from `backend/btc_onchain/rpc.py`.
3. Optionally creates a Fulcrum client from `backend/btc_onchain/core/fulcrum_client.py`.
4. Builds the application state object from `backend/btc_onchain/core/app_state.py`.
5. Starts background loops for mempool refresh, live estimation, and stencil caching.
6. Registers API routes from `backend/btc_onchain/api/routes.py` and `backend/btc_onchain/api/routes_prices.py`.

## Backend Layers

The active backend architecture is organized around these layers.

### 1. Transport and external access

- `backend/btc_onchain/rpc.py`
  - Minimal async JSON-RPC wrapper for Bitcoin Knots.
- `backend/btc_onchain/core/fulcrum_client.py`
  - Persistent Electrum/Fulcrum client for historical block transaction retrieval.
- `backend/btc_onchain/core/external_prices.py`
  - Optional external BTC/USD polling and SQLite persistence.

These modules should remain the only places that talk directly to external services.

### 2. Ingestion and caching

- `backend/btc_onchain/core/mempool_cache.py`
  - Pulls mempool transactions from Knots RPC.
  - Fetches raw transactions.
  - Extracts all outputs.
  - Assigns a heuristic weight based on output count and RBF status.
  - Stores outputs in a rolling in-memory window.
  - Tracks decoded transaction IDs across scans, bounded by current mempool membership and rolling retention; failed attempts consume the per-scan RPC budget.

- `backend/btc_onchain/core/stencil_cache.py`
  - Stores compact block-local eligible transaction inputs and amounts in a bounded cache keyed by block hash.
  - Uses bulk Knots block retrieval and validates complete Fulcrum fallback responses.
  - Shares cache misses across background/API requests; range-dependent spending exclusions remain in `stencil_price.py`.

This is the live input source for the nowcaster.

### 3. Estimation logic

- `backend/btc_onchain/core/rnr_engine.py`
  - Runs the live estimator loop.
  - Converts mempool outputs into `(value_btc, weight)` pairs.
  - Calls the live oracle.
  - Applies EMA smoothing.
  - Maintains curve and histogram debug state.
- `backend/btc_onchain/oracle/utxoracle_live.py`
  - Core live nowcasting logic.
  - Builds a log-BTC histogram.
  - Suppresses round-BTC artifacts.
  - Slides calibrated spike and smooth stencils.
  - Derives the best implied BTC/USD price.
  - Produces confidence, curvature, and curve points.
- `backend/btc_onchain/core/stencil_price.py`
  - Core historical estimator.
  - Fetches blocks over a chosen range.
  - Filters eligible transactions.
  - Builds a histogram over output values.
  - Slides a calibrated stencil over the histogram.
  - Produces an estimated price and round-dollar anchor stats.

### 4. Diagnostics and analysis

- `backend/btc_onchain/rnr.py`
  - Legacy RNR helpers still used for output weighting and debug USD histograms.
- `backend/btc_onchain/core/distribution_engine.py`
  - Computes output-size distributions for mempool and recent blocks.

### 5. API layer

- `backend/btc_onchain/api/routes.py`
  - Main backend API for health, price, curve, histogram, heatmap, distribution, block inspection, stencil estimation, and CSV export.
- `backend/btc_onchain/api/routes_prices.py`
  - Optional external price comparison endpoints.
- `backend/btc_onchain/models.py`
  - Pydantic response models shared across the API surface.

## Live Estimation Flow

The live estimator works like this:

1. `MempoolCache.scan_once()` calls `getrawmempool(true)` on the Knots node.
2. It selects recent unseen transactions, sorts them by mempool time, and attempts up to the configured decode budget.
3. For each decoded transaction, it extracts `vout` values and stores them as rolling `TxOut` entries.
4. `RnrEngine.run_loop()` periodically reads recent outputs from the cache.
5. It converts those outputs into weighted `(value_btc, weight)` pairs.
6. `estimate_from_outputs()` in `utxoracle_live.py` bins outputs in log-BTC space and performs stencil sliding.
7. The best slide is mapped into an implied BTC/USD price.
8. Confidence and curvature are computed from peak dominance and local peak shape.
9. The result is smoothed with EMA and exposed through `/price/now`.

## Historical Stencil Flow

The historical estimator works like this:

1. A client calls `/debug/stencil_price` with a block range or lookback.
2. The API resolves absolute block heights against the chain tip.
3. `compute_stencil_price()` reuses compact block-hash-keyed inputs, fetching cold blocks in bulk from Knots RPC with Fulcrum as a validated fallback.
4. Transactions are filtered to exclude coinbase and several non-target transaction patterns.
5. Eligible outputs are placed into log-BTC histogram bins.
6. A calibrated stencil is slid across the histogram.
7. The best slide and a neighbor slide are blended into a final estimated price.
8. Per-anchor stats are returned for known round-dollar values such as 100 USD, 500 USD, and 1000 USD.

This path is used both on demand and in the background stencil caching loop.
The background loop checks the current tip and recomputes only when the tip hash or selected range changes. The API validates the cached range's end hash before reuse, and both computation paths reject a chain change during the scan. Completed block inputs are cached independently of the same-window spending filter, which is recalculated for each range.

## Diagnostics and Visualization

The backend exposes several diagnostics used by the dashboard:

- `/price/now`
  - Current live nowcast.
- `/rnr/curve`
  - Live curve points from the nowcaster.
- `/debug/candidates`
  - Cached mempool output counts.
- `/debug/histogram`
  - USD anchor histogram centered around the current estimate.
- `/debug/heatmap`
  - Time-bucketed mempool output heatmap by sat ranges.
- `/debug/distribution`
  - Distribution of output sizes for mempool or historical blocks.
- `/debug/blocks`
  - Block range inspection.
- `/debug/stencil_price`
  - Historical stencil estimate.
- `/debug/mempool_csv`
  - CSV export of cached mempool outputs.
- `/debug/blocks_csv`
  - CSV export of historical block outputs.

Optional external comparison endpoints:

- `/external/price/sources`
- `/external/price/now`
- `/external/price/history`
- `/price/compare`

## Frontend Architecture

The frontend is a single dashboard application rooted in `frontend/src/App.tsx`.

It polls backend APIs on an interval and composes several visualization panels:

- `frontend/src/components/PriceCards.tsx`
  - Displays live price, stencil price, blended estimate, and gap.
- `frontend/src/components/CurveChart.tsx`
  - Displays the live estimator curve.
- `frontend/src/components/RoundNumberHistogram.tsx`
  - Shows clustering around round-dollar anchors.
- `frontend/src/components/TransactionsHeatmap.tsx`
  - Shows mempool output density over time and sat ranges.
- `frontend/src/components/RoundUsdHeatmap.tsx`
  - Displays historical round-dollar anchor intensity from stencil stats.
- `frontend/src/components/SatsDistributionPanel.tsx`
  - Shows mempool or block output-size distributions and overlays round-USD reference lines.
- `frontend/src/components/CandidatesPanel.tsx`
  - Displays mempool candidate counts.
- `frontend/src/components/ControlOverlay.tsx`
  - Controls grid, span, heatmap, block lookback, and distribution settings.

Shared frontend API access lives in `frontend/src/lib/api.ts`.
Shared frontend response types live in `frontend/src/lib/types.ts`.

## Configuration Model

Runtime configuration is centralized in `backend/btc_onchain/config.py`.

It includes:

- Knots RPC connection settings.
- Mempool scan cadence and lookback window.
- Price search and smoothing parameters.
- Histogram and heatmap settings.
- Distribution settings.
- Fulcrum settings.
- Optional external price polling settings.

Environment files are loaded from:

- `backend/local.env`
- `backend/.env`

## Active Architecture vs Legacy Files

There is architecture drift in the repository.

The active runtime path is based on:

- `backend/btc_onchain/main.py`
- `backend/btc_onchain/core/*`
- `backend/btc_onchain/api/*`
- `backend/btc_onchain/oracle/utxoracle_live.py`

There are also older files that appear stale and are not part of the current runtime design:

- `backend/btc_onchain/state.py`
- `backend/btc_onchain/workers.py`
- `backend/btc_onchain/types.py`

Those files reflect an earlier design and should not be treated as authoritative without verification.

## Architectural Strengths

- Clear separation between transport, caching, estimation, diagnostics, and API shaping.
- Live and historical estimators are conceptually separate.
- The frontend is thin and mostly consumes backend state rather than re-implementing business logic.
- Fulcrum integration is isolated to a dedicated client.

## Current Architectural Risks

- Some external price configuration names are inconsistent between `config.py`, `main.py`, and `routes_prices.py`.
- Some stale modules remain in the repository and can mislead future contributors.
- The older `rnr.py` naming can imply it is the main estimator, but the live estimator currently runs through `oracle/utxoracle_live.py`.
- The external price subsystem is intended as comparison-only, but that boundary should stay explicit in code and docs.

## Engineering Rules For Future Changes

- Keep Knots RPC access encapsulated in transport modules.
- Keep live mempool estimation separate from historical block stencil analysis.
- Keep optional external prices out of the core estimator path.
- Prefer pure functions for histogram, filtering, weighting, and stencil logic.
- Update this file when module boundaries or runtime flow change.

## Reading Order

For project initialization, read these files in order:

1. `agents.md`
2. `architecture.md`
3. `dev-protocol.md`
4. `todo.md`
5. `README.md`

Then follow any linked Markdown files recursively as needed.


## Shadow evaluation extension

`oracle/refined.py` is a pure on-chain candidate, called from the existing RNR loop. `core/evaluation.py` consumes model snapshots plus an isolated `external_prices.py` poller for monitoring only; it never writes to RnrEngine. `/price/evaluation` is the delivery boundary. Persistent statistics are recorded separately from estimator state. Candidate failures cannot interrupt the primary model. See README for constants and semantics.
