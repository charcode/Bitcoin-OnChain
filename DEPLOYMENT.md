# Deployment & Quickstart

This guide covers cloning the repo, running the backend and frontend locally, and deploying with Docker.

## 1) Clone the repository

```
git clone git@github.com:charcode/Bitcoin-OnChain.git
cd Bitcoin-OnChain
```

## 2) Local development

### Backend (FastAPI) — Conda

Requirements: Conda (Anaconda/Miniconda), a local Bitcoin node with RPC.

```
cd backend
conda env create -f environment.yaml   # creates env named "btc-onchain"
conda activate btc-onchain
uvicorn --host 127.0.0.1 --port 8000 btc_onchain.main:app
```

Environment variables (examples):

```
BTC_RPC_URL=http://127.0.0.1:8332
BTC_RPC_USER=youruser
BTC_RPC_PASS=yourpass
```

### Frontend (Vite/React)

```
cd frontend
npm install
npm run dev
```

The frontend expects `VITE_API_URL` (defaults to http://127.0.0.1:8000). Set it in `frontend/.env` if needed:

```
VITE_API_URL=http://127.0.0.1:8000
```

## 3) Docker Compose

Create a `.env` at the repo root:

```
BTC_RPC_URL=http://host.docker.internal:8332
BTC_RPC_USER=youruser
BTC_RPC_PASS=yourpass
VITE_API_URL=http://backend:8000
```

Example `docker-compose.yml`:

```
version: '3.9'
services:
  backend:
    build: ./backend
    command: uvicorn --host 0.0.0.0 --port 8000 btc_onchain.main:app
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped

  frontend:
    build: ./frontend
    environment:
      - VITE_API_URL=${VITE_API_URL}
    ports:
      - "5173:5173"
    depends_on:
      - backend
    restart: unless-stopped
```

Minimal Dockerfiles:

`backend/Dockerfile`

```
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
EXPOSE 8000
CMD ["uvicorn", "btc_onchain.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`frontend/Dockerfile`

```
FROM node:20-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app .
EXPOSE 5173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0"]
```

Run:

```
docker compose up --build
```

Backend: http://localhost:8000

Frontend: http://localhost:5173

Notes:

- On macOS/Windows, `host.docker.internal` lets the backend container reach your host’s Bitcoin Core RPC.
- For production, put a reverse proxy in front of the backend and serve the frontend as static assets.
