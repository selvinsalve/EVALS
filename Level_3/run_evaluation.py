#!/usr/bin/env python3
"""
CLI entrypoint for running DeepEval evaluations on RAG and Database Chatbot.
Usage:
    .venv/bin/python run_evaluation.py --all
    .venv/bin/python run_evaluation.py --rag
    .venv/bin/python run_evaluation.py --db
    .venv/bin/python run_evaluation.py --multiturn
    .venv/bin/python run_evaluation.py --multiturn --case conv_case_001
    .venv/bin/python run_evaluation.py --db --case db_cancel_eligible_001
    .venv/bin/python run_evaluation.py --list-cases
    .venv/bin/python run_evaluation.py --generate-goldens
    .venv/bin/python run_evaluation.py --all --max-cases 1
"""

import sys
import json
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluation.golden_generator import GoldenDatasetMasterGenerator
from evaluation.runner import EvaluationRunner
from evaluation.config import get_eval_settings


def list_cases():
    settings = get_eval_settings()
    suites = {
        "RAG": settings.GOLDEN_DATASETS_DIR / "rag_golden_dataset.json",
        "DATABASE_CHATBOT": settings.GOLDEN_DATASETS_DIR / "db_chatbot_golden_dataset.json",
        "MULTI_TURN": settings.GOLDEN_DATASETS_DIR / "multiturn_golden_dataset.json",
    }
    print("=" * 70)
    print(" Available Test Cases")
    print("=" * 70)
    for suite, path in suites.items():
        if path.exists():
            with open(path) as f:
                cases = json.load(f)
            print(f"\n[{suite}] ({len(cases)} cases in {path.name}):")
            for c in cases:
                desc = c.get("input") or c.get("scenario") or ""
                print(f"  • {c.get('id'):28s} : {desc[:60]}...")
        else:
            print(f"\n[{suite}] File not found: {path.name}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="DeepEval Evaluation Runner for RAG & Database-Backed Chatbot (Strictly JSON Output)"
    )
    parser.add_argument(
        "--generate-goldens",
        action="store_true",
        help="Generate and save golden datasets for RAG, DB, and Multi-turn without evaluating.",
    )
    parser.add_argument(
        "--list-cases",
        action="store_true",
        help="List all available test cases across all suites.",
    )
    parser.add_argument(
        "--rag",
        action="store_true",
        help="Run RAG evaluation suite.",
    )
    parser.add_argument(
        "--db",
        action="store_true",
        help="Run Database Chatbot evaluation suite.",
    )
    parser.add_argument(
        "--multiturn",
        action="store_true",
        help="Run Multi-Turn conversation evaluation suite.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all evaluation suites (RAG, DB Chatbot, Multi-Turn).",
    )
    parser.add_argument(
        "--case",
        type=str,
        default=None,
        help="Run evaluation for a specific test case ID (e.g. conv_case_001, db_tracking_001).",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Maximum number of test cases to evaluate per suite (useful for fast verification).",
    )

    args = parser.parse_args()

    # If no flags passed, display help
    if not any([args.generate_goldens, args.list_cases, args.rag, args.db, args.multiturn, args.all]):
        parser.print_help()
        sys.exit(0)

    if args.list_cases:
        list_cases()
        sys.exit(0)

    print("=" * 70)
    print(" DeepEval AI System Evaluation Framework")
    print("=" * 70)

    if args.generate_goldens:
        print("\n[*] Generating golden datasets...")
        master_gen = GoldenDatasetMasterGenerator()
        paths = master_gen.generate_and_save_all()
        for suite, path in paths.items():
            print(f"  - [{suite.upper()}] Golden dataset saved to: {path}")
        print("\n[OK] Golden generation complete.")
        if not any([args.rag, args.db, args.multiturn, args.all]):
            return

    runner = EvaluationRunner()

    if args.all:
        print(f"\n[*] Running FULL evaluation suite (max_cases={args.max_cases})...")
        runner.run_all(max_cases=args.max_cases)
    else:
        if args.rag:
            print(f"\n[*] Running RAG evaluation suite (case={args.case}, max_cases={args.max_cases})...")
            runner.run_rag_evaluation(max_cases=args.max_cases, case_id=args.case)
        if args.db:
            print(f"\n[*] Running Database Chatbot evaluation suite (case={args.case}, max_cases={args.max_cases})...")
            runner.run_db_evaluation(max_cases=args.max_cases, case_id=args.case)
        if args.multiturn:
            print(f"\n[*] Running Multi-Turn evaluation suite (case={args.case}, max_cases={args.max_cases})...")
            runner.run_multiturn_evaluation(max_cases=args.max_cases, case_id=args.case)

    print("\n" + "=" * 70)
    print(" Evaluation Completed. All reports saved as JSON under evaluation/reports/")
    print("=" * 70)


if __name__ == "__main__":
    main()
