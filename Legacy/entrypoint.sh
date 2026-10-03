#!/usr/bin/env bash
set -e

echo "==> Initializing Database..."
python scripts/init_db.py

echo "==> Seeding Demo Data..."
python scripts/seed_data.py

echo "==> Ingesting RAG Documents into ChromaDB..."
python scripts/ingest_documents.py

echo "==> Starting FastAPI Backend on port 8000..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

echo "==> Starting Streamlit Frontend on port 8501..."
streamlit run streamlit_app/app.py --server.port 8501 --server.address 0.0.0.0

wait -n
exit $?
