# Reproduce the Resonance setup

## What is Dockerized

The FastAPI backend and React/Vite dashboard are built from this repository. The optional old `docker-compose.yml` also packages Fulcrum and mounts an existing DATUM binary; it does not build a Bitcoin node or mine by itself. The current Alienware setup runs Bitcoin and Fulcrum as Windows services, DATUM under WSL, and the Pi monitor under systemd. This guide reproduces the web application against those external services. No wallet, index, RPC credential, node datadir or private SSH key belongs in Git.

## Fresh clone (Docker Desktop / Windows or macOS)

Install Git and Docker Compose v2, provide a synchronized mainnet Bitcoin Core/Knots node with authenticated RPC, then:

```sh
git clone https://github.com/charcode/Bitcoin-OnChain.git
cd Bitcoin-OnChain
cp .env.example .env
# Edit .env locally: BTC_RPC_USER, BTC_RPC_PASS and the reachable BTC_RPC_URL.
docker compose --env-file .env -f compose.repro.yml config --quiet
docker compose --env-file .env -f compose.repro.yml up -d --build
```

PowerShell uses `Copy-Item .env.example .env` instead of `cp` if preferred. Docker Desktop's `host.docker.internal` reaches host services; verify reachability without changing Bitcoin RPC to an unrestricted LAN/public bind. Keep authentication, firewall restrictions and existing secure forwarding in place. No private data is supplied or initialized by the application. Fulcrum is optional for the live estimator and defaults off in the portable setup.

Open http://127.0.0.1:5173. Health: http://127.0.0.1:8000/health. Evaluation: http://127.0.0.1:8000/price/evaluation. Wait for at least 500 eligible cached outputs and fresh exchange quotes; sparse/ambiguous candidates correctly remain unavailable. Exchanges are monitoring-only and require outbound HTTPS.

For LAN browsing, set `BIND_ADDRESS=0.0.0.0` and `VITE_API_URL=http://YOUR_LAN_IP:8000`, restrict host firewall access to your LAN, and rebuild the frontend. The browser must reach this URL directly. Never expose the node's RPC port publicly. Browser URLs and port changes require matching configuration.

## Native Linux / loopback-only Core

`host-gateway` does not make a host-loopback listener reachable on native Linux. Use the supplied backend-only host-network override (Compose 2.24.4+ for `!reset`), not an unrestricted Bitcoin bind:

```sh
docker compose --env-file .env -f compose.repro.yml -f compose.linux-host.yml up -d --build
```

Core remains at 127.0.0.1:8332; this override exposes the web API using its normal host listener. Apply the host firewall appropriate to the intended web clients. The frontend remains bridged. This Linux override is documented but has not been exercised on the Windows deployment host.

## Tests and reproducibility boundary

```sh
docker compose --env-file .env -f compose.repro.yml build backend frontend
docker compose --env-file .env -f compose.repro.yml run --rm --no-deps -v "${PWD}/backend/tests:/tests:ro" backend python -m unittest discover -s /tests -v
```

Thirty deterministic backend tests currently cover estimator fixtures, abstention, freshness, typed API responses, paired SQLite persistence, ingestion and historical caching. Python 3.11 dependencies are pinned in `backend/requirements.lock`; frontend dependencies use `package-lock.json` and `npm ci`. Platform images still use public version tags, so builds are functionally reproducible, not claimed byte-for-byte identical. The lock reflects Linux/amd64 deployment; Apple Silicon/ARM compatibility must be validated separately.

The experimental candidate remains SHADOW; legacy remains primary. The cyan band is kernel/model sensitivity, not a calibrated confidence interval or a promised error bound. No exchange-price correction or flat dollar offset is applied. Retain at least seven days of prospective paired observations and held-out replays before promotion.

## Persistence, backup and rollback

Named volume `evaluation` contains comparison prices, model versions/quality and paired measurements with 14-day retention. Back up the volume using a stopped/consistent SQLite snapshot before migration. `docker compose ... down` preserves it; `down -v` destroys it and is not a normal upgrade step. Existing blockchain/Fulcrum data is external and untouched.

For the existing Alienware installation, use its original C:/BitcoinLANPortal base Compose file with `docker-compose.price-shadow.yml` documented in README. The source-only `compose.repro.yml` above avoids dependencies on the private `before-price-shadow` images. Do not launch it beside the running production stack on the same ports. Current rollback images/source backups and live runtime overlays are operational artifacts, not required to clone/build this source.

## Integrated console and UTXO Lab

See https://github.com/charbelgereige/bitnode_monitor/tree/feature/add-template-error-monitoring and its `SETUP.md`. That repository supplies a portable combined console/UTXO/Resonance Compose stack, the historical output lifecycle scanner and Telegram command integration. The Pi monitor is deployed natively under systemd because it needs host journals, bitcoin-cli and service controls.

## Credentials previously tracked

Runtime environment files were present in earlier repository history. This change untracks them without deleting the live files and excludes new credentials. It does not erase old history. Rotate any live credentials that were stored there according to the deployment's maintenance procedure; do not paste them into issues, docs or build arguments.

Non-secret active model settings are recorded in [deploy/alienware-model-settings.json](deploy/alienware-model-settings.json). The root template mirrors the deployed 30,000–1,000,000 supported-price bounds; these are validation bounds, not evidence that every price in that interval can be estimated accurately.


### Shared computation and persistent derived data
Run one backend process (the provided Docker command does this). All viewers
share its live producer; opening a browser does not start another model loop.
`/data/model_cache.sqlite` beside the evaluation DB stores bounded compact block
inputs, historical range results and the last 600 live history points. Set
`MODEL_CACHE_DB` to override this path. Preserve the named evaluation volume.
Historical keys include canonical end hash; reorgs invalidate old range results.
Concurrent requests share one computation; custom ranges can still incur a cold
calculation, once per range/hash. Live data warms up again after restart; restored
history retains original timestamps and is never presented as a fresh quote.
An unchanged live input set does not rerun inference. Freshness can therefore
expire when ingestion stops, instead of an unchanged result being relabelled fresh.
Do not add Uvicorn workers or replicas: scaling the API requires moving the single
producer to a separate service and distributing its read model.

Cold historical HTTP requests return 503 with Retry-After while shared work continues; the UI retries every 10 seconds. Automation can use `wait=true` to await that same job. Cache diagnostics are available at `/debug/shared_cache`.
