"""
Unified facade for generating and persisting all evaluation golden datasets.
"""

from pathlib import Path
from typing import Dict
from evaluation.config import get_eval_settings
from evaluation.golden_generator.rag_generator import RAGGoldenDatasetGenerator
from evaluation.golden_generator.db_generator import DBGoldenDatasetGenerator
from evaluation.golden_generator.multiturn_generator import MultiTurnGoldenDatasetGenerator


class GoldenDatasetMasterGenerator:
    """Coordinates generation and persistence of all golden datasets."""

    def __init__(self):
        self.settings = get_eval_settings()
        self.rag_gen = RAGGoldenDatasetGenerator()
        self.db_gen = DBGoldenDatasetGenerator()
        self.mt_gen = MultiTurnGoldenDatasetGenerator()

    def generate_and_save_all(self) -> Dict[str, Path]:
        saved_paths = {}
        saved_paths["rag"] = self.rag_gen.save_to_file()
        saved_paths["db"] = self.db_gen.save_to_file()
        saved_paths["multiturn"] = self.mt_gen.save_to_file()
        return saved_paths
