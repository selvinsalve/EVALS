#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Activate virtual environment if present
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo "=========================================================="
echo " Starting AI Order Assistant (Level_3)"
echo " Backend:   http://localhost:8000 (Docs: http://localhost:8000/docs)"
echo " Frontend:  http://localhost:8501 (Streamlit UI)"
echo "=========================================================="

# Start backend in background
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Start Streamlit frontend
streamlit run streamlit_app/app.py --server.port 8501 --server.address 0.0.0.0

kill $BACKEND_PID 2>/dev/null || true
