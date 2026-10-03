#!/usr/bin/env python3
"""Seed the database with customers, orders, order items, and shipments."""
import sys
from pathlib import Path

# Ensure root project directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.database.seed import init_db, seed_data
from app.utils.logging import logger

if __name__ == "__main__":
    logger.info("Initializing tables and seeding demo data...")
    init_db()
    seed_data()
    logger.info("Seed data process completed.")
