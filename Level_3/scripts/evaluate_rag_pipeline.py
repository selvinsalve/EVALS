#!/usr/bin/env python3
"""
CLI Batch Evaluation Script for RAG Pipelines using DeepEval.
Evaluates Faithfulness, Answer Relevance, Contextual Relevancy, Precision, and Recall.
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
    parser = argparse.ArgumentParser(description="Evaluate RAG pipeline using DeepEval metrics.")
    parser.add_argument(
        "--goldens",
        type=str,
        default=str(BASE_DIR / "data" / "golden_eval_dataset.json"),
        help="Path to JSON file containing golden test cases.",
    )
    parser.add_argument(
        "--metrics",
        type=str,
        default="faithfulness,answer_relevancy,contextual_relevancy,contextual_precision,contextual_recall",
        help="Comma-separated metric names to evaluate.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of test cases to evaluate (useful for rapid debugging).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Query live Assistant/RAG pipeline to obtain actual_output before evaluating.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Ollama model override (e.g. qwen2.5:7b-instruct-q4_K_M).",
    )

    args = parser.parse_args()

    goldens_file = Path(args.goldens)
    if not goldens_file.exists():
        logger.error("Golden dataset not found at: %s", goldens_file)
        sys.exit(1)

    with open(goldens_file, "r", encoding="utf-8") as f:
        goldens = json.load(f)

    if args.limit:
        goldens = goldens[:args.limit]

    metric_names = [m.strip() for m in args.metrics.split(",") if m.strip()]
    logger.info("Loaded %d goldens. Evaluating with metrics: %s", len(goldens), metric_names)

    # Initialize Runner
    config = EvaluationConfig()
    if args.model:
        config.ollama_model = args.model

    runner = EvaluationRunner(config=config)

    if args.live:
        logger.info("Executing RAG evaluation against LIVE assistant & retriever...")
        summary = runner.run_rag_eval_against_live_system(
            goldens=goldens,
            metric_names=metric_names,
            save_report=True,
            use_assistant=True,
        )
    else:
        logger.info("Executing RAG evaluation using golden contexts and answers...")
        # Prepare inputs from goldens
        test_inputs = []
        for g in goldens:
            test_inputs.append({
                "id": g.get("id"),
                "input": g["input"],
                "actual_output": g.get("actual_output") or g["expected_output"],
                "retrieval_context": g.get("context") or g.get("retrieval_context", ["General policy"]),
                "expected_output": g.get("expected_output"),
            })
        summary = runner.rag_evaluator.evaluate_batch(test_cases=test_inputs, metric_names=metric_names)
        report_path = runner.save_json_report(summary)
        runner.print_console_summary(summary)
        logger.info("Saved evaluation report to: %s", report_path)

    # Exit code based on pass rate for CI/CD pipelines
    if summary.pass_rate < 50.0:
        logger.warning("Evaluation pass rate (%.1f%%) below target threshold (50%%).", summary.pass_rate)
        sys.exit(1)
    else:
        logger.info("Evaluation completed successfully with pass rate: %.1f%%", summary.pass_rate)
        sys.exit(0)


if __name__ == "__main__":
    main()
