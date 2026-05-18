# Deployment & Quickstart

This guide covers cloning the repo, running the backend and frontend locally, and deploying with Docker.

## 1) Clone the repository

```powershell
git clone git@github.com:charcode/Bitcoin-OnChain.git
cd Bitcoin-OnChain
```

## 2) Local Development

### Backend (FastAPI) - Conda

Requirements: Conda or Miniconda, plus a local Bitcoin node with RPC enabled.

```powershell
cd backend
conda env create -f environment.yaml
conda activate btc-onchain
uvicorn --host 127.0.0.1 --port 8000 btc_onchain.main:app
```

Environment variables:

```powershell
BTC_RPC_URL=http://127.0.0.1:8332
BTC_RPC_USER=youruser
BTC_RPC_PASS=yourpass
```

### Frontend (Vite/React)

```powershell
cd frontend
npm install
npm run dev
```

The frontend expects `VITE_API_URL`, defaulting to `http://127.0.0.1:8000`.

## 3) Docker Compose

Copy the Docker environment template and edit credentials and host paths:

```powershell
copy .env.docker.example .env.docker
```

Run the monitoring stack:

```powershell
docker compose --env-file .env.docker --profile monitoring up --build
```

Run monitoring plus the Datum mining gateway:

```powershell
docker compose --env-file .env.docker --profile monitoring --profile mining up --build
```

Backend: http://localhost:8000

Frontend: http://localhost:5173

Notes:

- On Windows Docker Desktop, `host.docker.internal` lets containers reach your host Bitcoin Knots RPC.
- The Datum service mounts the existing Linux build directory from `DATUM_GATEWAY_BUILD` and runs `./datum_gateway -c config.json`.
- The Fulcrum service uses the Linux Fulcrum release. The Windows `Fulcrum.exe` path is not executable inside a Linux Docker container.
- Update `fulcrum.conf` so container-local paths use `/data/fulcrum`, and point Bitcoin RPC/P2P hosts at `host.docker.internal` when the Bitcoin node runs on the Windows host.
- For production, put a reverse proxy in front of the backend and serve the frontend as static assets.
