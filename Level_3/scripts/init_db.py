#!/usr/bin/env python3
"""Initialize database tables."""
import sys
from pathlib import Path

# Ensure root project directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.database.seed import init_db
from app.utils.logging import logger

if __name__ == "__main__":
    logger.info("Running database initialization...")
    init_db()
    logger.info("Database initialized successfully.")
