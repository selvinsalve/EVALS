#!/usr/bin/env python3
"""
CLI Batch Evaluation Script for Multi-Turn Conversational Quality using DeepEval.
Evaluates Turn Relevancy, Turn Faithfulness, Role Adherence, Completeness, and Coherence.
"""
import sys
import json
import argparse
from pathlib import Path

# Ensure root project directory is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.evaluation.config import EvaluationConfig
from app.evaluation.runner import EvaluationRunner
from app.utils.logging import logger


def main():
    parser = argparse.ArgumentParser(description="Evaluate multi-turn chat sessions using DeepEval.")
    parser.add_argument(
        "--sessions",
        type=str,
        default=str(BASE_DIR / "data" / "sample_chat_sessions.json"),
        help="Path to JSON file containing multi-turn chat sessions.",
    )
    parser.add_argument(
        "--metrics",
        type=str,
        default="role_adherence,conversation_completeness,turn_relevancy,turn_faithfulness,conversational_coherence,knowledge_retention",
        help="Comma-separated conversational metric names to evaluate.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of sessions to evaluate.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Ollama model override.",
    )

    args = parser.parse_args()

    sessions_file = Path(args.sessions)
    if not sessions_file.exists():
        logger.error("Chat sessions file not found at: %s", sessions_file)
        sys.exit(1)

    with open(sessions_file, "r", encoding="utf-8") as f:
        sessions = json.load(f)

    if args.limit:
        sessions = sessions[:args.limit]

    metric_names = [m.strip() for m in args.metrics.split(",") if m.strip()]
    logger.info("Loaded %d chat sessions. Evaluating with metrics: %s", len(sessions), metric_names)

    config = EvaluationConfig()
    if args.model:
        config.ollama_model = args.model

    runner = EvaluationRunner(config=config)
    summary = runner.run_conversational_eval_from_logs(
        sessions=sessions,
        metric_names=metric_names,
        save_report=True,
    )

    if summary.pass_rate < 50.0:
        logger.warning("Conversational evaluation pass rate (%.1f%%) below target threshold.", summary.pass_rate)
        sys.exit(1)
    else:
        logger.info("Conversational evaluation completed successfully with pass rate: %.1f%%", summary.pass_rate)
        sys.exit(0)


if __name__ == "__main__":
    main()
