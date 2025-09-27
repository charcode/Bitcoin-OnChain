.
├─ backend/            # Python package `btc_onchain` + FastAPI app
│  └─ btc_onchain/
│     ├─ main.py       # FastAPI app (import path: btc_onchain.main:app)
│     ├─ config.py     # env vars & defaults
│     ├─ rpc.py        # Rpc class (final)
│     ├─ mempool.py    # Mempool scanner/cache
│     ├─ rnr.py        # RNR search + histogram
│     └─ state.py      # AppState and RnrEngine
└─ frontend/           # React + Vite dashboard (TypeScript)
   ├─ index.html
   └─ src/
      ├─ main.tsx
      ├─ App.tsx
      ├─ components/ (e.g., CurveChart, DebugBar, PriceCards, CandidatesPanel)
      └─ lib/ (api.ts, types.ts)
