import json
import time
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from app.config import get_settings
from app.utils.logging import logger
from app.evaluation.config import EvaluationConfig
from app.evaluation.rag_evaluator import RAGEvaluator
from app.evaluation.conversational_evaluator import ConversationalEvaluator
from app.evaluation.models import BatchEvaluationSummary, RAGTestCaseInput

settings = get_settings()


class EvaluationRunner:
    """
    Test harness orchestrating batch evaluation runs for RAG pipelines and chat sessions.
    Saves JSON reports and displays structured console summaries for CI/CD integration.
    """

    def __init__(self, config: Optional[EvaluationConfig] = None):
        self.config = config or EvaluationConfig()
        self.rag_evaluator = RAGEvaluator(config=self.config)
        self.conv_evaluator = ConversationalEvaluator(config=self.config)
        self.reports_dir = Path(settings.DATA_DIR) / "eval_reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def run_rag_eval_against_live_system(
        self,
        goldens: List[Dict[str, Any]],
        metric_names: Optional[List[str]] = None,
        save_report: bool = True,
        use_assistant: bool = True,
    ) -> BatchEvaluationSummary:
        """
        Execute goldens against the live RAG / Assistant pipeline, capturing live retrieval context
        and generated responses, then evaluating them against expected outputs.
        """
        from app.database.database import SessionLocal
        from app.services.assistant_service import AssistantService
        from app.services.rag_service import RAGService

        logger.info("Executing %d goldens against live RAG/Assistant system...", len(goldens))
        rag_inputs: List[RAGTestCaseInput] = []

        db = SessionLocal()
        try:
            assistant = AssistantService(db=db) if use_assistant else None
            rag_service = RAGService()

            for idx, g in enumerate(goldens, 1):
                query = g.get("input") or g.get("query", "")
                expected = g.get("expected_output") or g.get("ground_truth")
                reference_context = g.get("context")

                if use_assistant and assistant:
                    # Run full Assistant pipeline (intent + RAG + grounded synthesis)
                    response = assistant.process_message(user_message=query)
                    actual_output = response.answer
                    retrieval_chunks = [c.excerpt for c in response.sources] if response.sources else []
                    if not retrieval_chunks and response.used_rag:
                        ctx, _ = rag_service.get_policy_context(query)
                        retrieval_chunks = [ctx] if ctx else []
                else:
                    # Direct RAG retrieval evaluation
                    ctx, citations = rag_service.get_policy_context(query)
                    actual_output = ctx[:300] + "..." if ctx else "No context retrieved."
                    retrieval_chunks = [c.excerpt for c in citations] if citations else [ctx]

                if not retrieval_chunks:
                    retrieval_chunks = reference_context if reference_context else ["No context retrieved."]

                rag_inputs.append(
                    RAGTestCaseInput(
                        id=g.get("id") or f"golden_{idx}",
                        input=query,
                        actual_output=actual_output,
                        retrieval_context=retrieval_chunks,
                        expected_output=expected,
                        context=reference_context,
                        metadata=g.get("additional_metadata") or g.get("metadata"),
                    )
                )
        finally:
            db.close()

        summary = self.rag_evaluator.evaluate_batch(test_cases=rag_inputs, metric_names=metric_names)

        if save_report:
            report_path = self.save_json_report(summary)
            logger.info("Saved RAG evaluation report to: %s", report_path)

        self.print_console_summary(summary)
        return summary

    def run_conversational_eval_from_logs(
        self,
        sessions: List[Dict[str, Any]],
        metric_names: Optional[List[str]] = None,
        save_report: bool = True,
    ) -> BatchEvaluationSummary:
        """
        Evaluate recorded multi-turn chat sessions and logs.
        """
        logger.info("Executing conversational evaluation on %d chat sessions...", len(sessions))
        summary = self.conv_evaluator.evaluate_batch_sessions(sessions=sessions, metric_names=metric_names)

        if save_report:
            report_path = self.save_json_report(summary)
            logger.info("Saved Conversational evaluation report to: %s", report_path)

        self.print_console_summary(summary)
        return summary

    def save_json_report(self, summary: BatchEvaluationSummary) -> Path:
        """Write evaluation results to a structured JSON report file."""
        filename = f"{summary.evaluation_type.lower()}_report_{summary.run_id}.json"
        target_path = self.reports_dir / filename
        target_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        return target_path

    @staticmethod
    def print_console_summary(summary: BatchEvaluationSummary) -> None:
        """Print a structured, readable summary to console for terminal & CI/CD logs."""
        border = "=" * 80
        divider = "-" * 80

        print(f"\n{border}")
        print(f" DEEPEVAL {summary.evaluation_type.upper()} EVALUATION REPORT (Run: {summary.run_id})")
        print(f"{border}")
        print(f" Timestamp:      {summary.timestamp}")
        print(f" Judge Model:    {summary.model_used}")
        print(f" Total Cases:    {summary.total_test_cases}")
        print(f" Passed:         {summary.passed_test_cases} | Failed: {summary.failed_test_cases}")
        print(f" Pass Rate:      {summary.pass_rate}%")
        print(f" Execution Time: {summary.total_execution_time_seconds}s")
        print(f"{divider}")
        print(" METRIC SCORE AVERAGES:")
        for m_name, avg in summary.metric_averages.items():
            bar = "█" * int(avg * 20) + "░" * (20 - int(avg * 20))
            print(f"  • {m_name:<28} : {avg:.3f} / 1.000 [{bar}]")
        print(f"{divider}")

        # Highlight individual results
        print(" CASE BREAKDOWN:")
        for idx, item in enumerate(summary.results, 1):
            if summary.evaluation_type == "RAG":
                title = f"Case #{idx} [{item.test_case_id or 'N/A'}]"
                status_str = "PASSED" if item.overall_passed else "FAILED"
                print(f"\n  {title} -> {status_str} (Avg: {item.average_score:.2f})")
                print(f"    Query: {item.input[:75]}...")
                for m_name, m_res in item.metrics.items():
                    pass_char = "✓" if m_res.passed else "✗"
                    print(f"      [{pass_char}] {m_name}: {m_res.score:.2f} (thresh: {m_res.threshold})")
                    if m_res.reason and not m_res.passed:
                        print(f"          Reason: {m_res.reason[:100]}...")
            else:
                title = f"Session #{idx} [{item.session_id or 'N/A'}] ({item.total_turns} turns)"
                status_str = "PASSED" if item.overall_passed else "FAILED"
                print(f"\n  {title} -> {status_str} (Avg: {item.average_score:.2f})")
                if item.scenario:
                    print(f"    Scenario: {item.scenario}")
                for m_name, m_res in item.metrics.items():
                    pass_char = "✓" if m_res.passed else "✗"
                    print(f"      [{pass_char}] {m_name}: {m_res.score:.2f} (thresh: {m_res.threshold})")
                    if m_res.reason and not m_res.passed:
                        print(f"          Reason: {m_res.reason[:100]}...")

        print(f"\n{border}\n")
