# TODO

## Active Feature

- Deployed (2026-10-18): visible USD benchmark errors, shadow raw-amount refinement/sensitivity bands, stale-data controls, and responsive CSS repair. Thirty tests pass. Next: prospective paired validation and review of published reproduction setup; candidate remains experimental.

- Done (2026-10-13): remove duplicate mempool ingestion, reuse compact historical inputs by block hash, skip unchanged background windows, and vectorize diagnostic histogram windows. Twenty regression tests pass in the deployed image; only the backend was redeployed. Warm samples: CPU 6.95–13.72% of one core, RAM about 180 MiB; full 144-block stencil API responded in 208 ms. Existing edits, previous image, and source backups retained.

- Done: package the local mining gateway, Fulcrum, backend API, and frontend dashboard into Docker images and a Docker Compose workflow; stack startup now depends on local `.env.docker` credentials and container-valid Fulcrum paths.
- In progress: simplify the hero metrics, remove repetitive top-row entries, and restore a single dominant live price banner with red/green tick color and compact delta text.
- In progress: full frontend redesign into a premium market-intelligence interface with a dominant resonance chart, compact estimate timeline, progressive controls, and diagnostics drawer.

## Documentation

- Keep `README.md` aligned with the actual backend and frontend structure.
- Document the provenance of stencil constants and round-number calibration values.
- Add dedicated research notes for transaction filtering assumptions and known estimator failure modes.

## Backend Engineering

- Add a backend test suite for `rnr.py`, `core/stencil_price.py`, `core/mempool_cache.py`, and `core/distribution_engine.py`.
- Refactor any mixed-responsibility modules so RPC access, feature extraction, and scoring stay isolated.
- Audit the optional external price routes and config wiring so debug-only comparison code cannot leak into the core estimator path.
- Create reproducible fixtures for historical block windows and synthetic mempool snapshots.
- Add structured logging around estimator runs, cache state, and failure reasons.

## Data And Research

- Define the exact transaction eligibility rules for both mempool and historical block analysis.
- Evaluate how sensitive the estimator is to lookback windows, sigma, price-step resolution, and round-dollar grid selection.
- Benchmark the stencil estimate and mempool nowcaster against known historical windows.
- Identify failure regimes such as low-activity periods, fee spikes, exchange batching artifacts, and abnormal witness-heavy traffic.

## Frontend

- Replace the template-style frontend README with project-specific frontend instructions.
- Document how each chart maps to backend endpoints and estimator concepts.
- Add UI states for missing data, stale data, and disabled external comparison feeds.

## Dev Process

- Add lint, test, and formatting commands to the root documentation.
- Decide on a formal branching and review workflow.
- Define a release checklist for research snapshots and dashboard deployments.
