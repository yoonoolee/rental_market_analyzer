# Real Estate AIgent

## Starting localhost

To start the app, always build the frontend first, then start the backend:

```bash
cd frontend && npm run build && cd ..
uvicorn server:app --reload --port 8000
```

Or use the convenience script:

```bash
./start.sh
```

The app is served at **http://localhost:8000** (FastAPI serves the built frontend from `frontend/dist`). Do NOT use port 5173 — that's the Vite dev server and is not needed.
