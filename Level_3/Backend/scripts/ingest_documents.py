#!/usr/bin/env python3
"""Ingest policy and FAQ documents into the ChromaDB vector database."""
import sys
from pathlib import Path

# Ensure root project directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.rag.ingest import run_ingestion
from app.rag.vector_store import VectorStoreManager
from app.utils.logging import logger

if __name__ == "__main__":
    logger.info("Starting document ingestion into ChromaDB...")
    num_chunks = run_ingestion()
    vs = VectorStoreManager()
    logger.info("Ingestion completed. Total document chunks stored in ChromaDB: %d", vs.count())
