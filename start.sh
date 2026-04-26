#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "Building frontend..."
cd frontend && npm run build && cd ..
echo "Starting server at http://localhost:8000"
uvicorn server:app --reload --port 8000
