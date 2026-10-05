"""
Evaluation Runner & Report Generator.
Orchestrates:
1. Loading or generating golden datasets
2. Executing black-box application interactions via client adapter
3. Evaluating via DeepEval metrics
4. Compiling aggregated pass rates and metric scores
5. Saving strictly JSON reports in evaluation/reports/ (NO markdown reports)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict
from evaluation.config import get_eval_settings, get_eval_model
from evaluation.models import (
    RAGGoldenCase,
    DBGoldenCase,
    MultiTurnGoldenCase,
    CaseEvaluationResult,
    EvaluationReport,
)
from evaluation.client_adapter import BaseAppAdapter, DirectServiceAdapter
from evaluation.evaluators.rag_evaluator import RAGEvaluator
from evaluation.evaluators.db_evaluator import DatabaseChatbotEvaluator
from evaluation.evaluators.multiturn_evaluator import MultiTurnEvaluator
from evaluation.golden_generator.rag_generator import RAGGoldenDatasetGenerator
from evaluation.golden_generator.db_generator import DBGoldenDatasetGenerator
from evaluation.golden_generator.multiturn_generator import MultiTurnGoldenDatasetGenerator


class EvaluationRunner:
    """End-to-end evaluation runner producing exclusively JSON reports."""

    def __init__(self, adapter: Optional[BaseAppAdapter] = None):
        self.settings = get_eval_settings()
        self.adapter = adapter or DirectServiceAdapter()
        self.eval_model = get_eval_model(self.settings)

    def _reset_test_orders(self):
        """Restore orders modified during evaluation (e.g. cancellations) to clean initial state."""
        import sqlite3
        try:
            conn = sqlite3.connect(str(self.settings.DB_PATH))
            c = conn.cursor()
            c.execute('UPDATE orders SET status = "PLACED", cancellation_allowed = 1 WHERE order_id = "ORD-1007"')
            conn.commit()
            conn.close()
        except Exception:
            pass

    def run_rag_evaluation(
        self,
        goldens: Optional[List[RAGGoldenCase]] = None,
        max_cases: Optional[int] = None,
        case_id: Optional[str] = None,
    ) -> EvaluationReport:
        """Executes black-box RAG evaluation and returns strictly JSON-serializable report."""
        if goldens is None:
            goldens_file = self.settings.GOLDEN_DATASETS_DIR / "rag_golden_dataset.json"
            if not goldens_file.exists():
                goldens_file = self.settings.GOLDEN_DATASETS_DIR / "rag_goldens.json"
            if not goldens_file.exists():
                RAGGoldenDatasetGenerator().save_to_file(goldens_file)
            with open(goldens_file, "r", encoding="utf-8") as f:
                raw_cases = json.load(f)
                goldens = [RAGGoldenCase(**c) for c in raw_cases]

        if case_id:
            goldens = [c for c in goldens if c.id == case_id]
            if not goldens:
                raise ValueError(f"Case ID '{case_id}' not found in RAG dataset.")

        if max_cases:
            goldens = goldens[:max_cases]

        evaluator = RAGEvaluator(model=self.eval_model)
        case_results: List[CaseEvaluationResult] = []

        for idx, case in enumerate(goldens, 1):
            print(f"[RAG Eval] Running case {idx}/{len(goldens)}: {case.id} - '{case.input[:50]}...'")
            captured = self.adapter.query_rag(case.input)
            result = evaluator.evaluate_case(golden=case, app_response=captured)
            case_results.append(result)

        report = self._build_report(
            eval_type="RAG",
            case_results=case_results,
        )
        self.save_report_json(report, filename=f"rag_evaluation_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
        return report

    def run_db_evaluation(
        self,
        goldens: Optional[List[DBGoldenCase]] = None,
        max_cases: Optional[int] = None,
        case_id: Optional[str] = None,
    ) -> EvaluationReport:
        """Executes black-box database chatbot evaluation and returns strictly JSON-serializable report."""
        if goldens is None:
            goldens_file = self.settings.GOLDEN_DATASETS_DIR / "db_chatbot_golden_dataset.json"
            if not goldens_file.exists():
                goldens_file = self.settings.GOLDEN_DATASETS_DIR / "db_chatbot_goldens.json"
            if not goldens_file.exists():
                DBGoldenDatasetGenerator().save_to_file(goldens_file)
            with open(goldens_file, "r", encoding="utf-8") as f:
                raw_cases = json.load(f)
                goldens = [DBGoldenCase(**c) for c in raw_cases]

        if case_id:
            goldens = [c for c in goldens if c.id == case_id]
            if not goldens:
                raise ValueError(f"Case ID '{case_id}' not found in DB dataset.")

        if max_cases:
            goldens = goldens[:max_cases]

        evaluator = DatabaseChatbotEvaluator(model=self.eval_model)
        case_results: List[CaseEvaluationResult] = []

        try:
            for idx, case in enumerate(goldens, 1):
                print(f"[DB Chatbot Eval] Running case {idx}/{len(goldens)}: {case.id} - '{case.input[:50]}...'")
                captured = self.adapter.query_chat(
                    query=case.input,
                    customer_id=case.customer_id,
                    conversation_history=None,
                )
                result = evaluator.evaluate_case(golden=case, app_response=captured)
                case_results.append(result)
        finally:
            self._reset_test_orders()

        report = self._build_report(
            eval_type="DATABASE_CHATBOT",
            case_results=case_results,
        )
        self.save_report_json(report, filename=f"db_evaluation_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
        return report

    def run_multiturn_evaluation(
        self,
        goldens: Optional[List[MultiTurnGoldenCase]] = None,
        max_cases: Optional[int] = None,
        case_id: Optional[str] = None,
    ) -> EvaluationReport:
        """Executes multi-turn conversation evaluation and returns strictly JSON-serializable report."""
        if goldens is None:
            goldens_file = self.settings.GOLDEN_DATASETS_DIR / "multiturn_golden_dataset.json"
            if not goldens_file.exists():
                goldens_file = self.settings.GOLDEN_DATASETS_DIR / "multiturn_chat_goldens.json"
            if not goldens_file.exists():
                MultiTurnGoldenDatasetGenerator().save_to_file(goldens_file)
            with open(goldens_file, "r", encoding="utf-8") as f:
                raw_cases = json.load(f)
                goldens = [MultiTurnGoldenCase(**c) for c in raw_cases]

        if case_id:
            goldens = [c for c in goldens if c.id == case_id]
            if not goldens:
                raise ValueError(f"Case ID '{case_id}' not found in multi-turn dataset.")

        if max_cases:
            goldens = goldens[:max_cases]

        evaluator = MultiTurnEvaluator(adapter=self.adapter, model=self.eval_model)
        case_results: List[CaseEvaluationResult] = []

        try:
            for idx, case in enumerate(goldens, 1):
                print(f"[Multi-Turn Eval] Running case {idx}/{len(goldens)}: {case.id} - '{case.scenario[:50]}...'")
                result = evaluator.evaluate_case(golden=case)
                case_results.append(result)
        finally:
            self._reset_test_orders()

        report = self._build_report(
            eval_type="MULTI_TURN",
            case_results=case_results,
        )
        self.save_report_json(report, filename=f"multiturn_evaluation_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
        return report

    def run_all(self, max_cases: Optional[int] = None) -> Dict[str, EvaluationReport]:
        """Runs all three evaluation suites and saves individual & combined JSON reports."""
        rag_report = self.run_rag_evaluation(max_cases=max_cases)
        db_report = self.run_db_evaluation(max_cases=max_cases)
        mt_report = self.run_multiturn_evaluation(max_cases=max_cases)

        combined = {
            "rag": rag_report.model_dump(mode="json"),
            "database_chatbot": db_report.model_dump(mode="json"),
            "multi_turn": mt_report.model_dump(mode="json"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "rag_pass_rate": rag_report.overall_pass_rate,
                "db_pass_rate": db_report.overall_pass_rate,
                "multiturn_pass_rate": mt_report.overall_pass_rate,
            },
        }

        combined_path = self.settings.REPORTS_DIR / f"full_evaluation_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        with open(combined_path, "w", encoding="utf-8") as f:
            json.dump(combined, f, indent=2)
        print(f"\n[OK] Combined JSON report saved to: {combined_path}")

        return {
            "rag": rag_report,
            "database_chatbot": db_report,
            "multi_turn": mt_report,
        }

    def _build_report(
        self,
        eval_type: str,
        case_results: List[CaseEvaluationResult],
    ) -> EvaluationReport:
        total = len(case_results)
        passed = sum(1 for c in case_results if c.all_passed)
        failed = total - passed
        pass_rate = (passed / total) if total > 0 else 0.0

        # Calculate metric averages and pass rates
        metric_scores: Dict[str, List[float]] = {}
        metric_passes: Dict[str, List[bool]] = {}

        for c in case_results:
            for m in c.metrics:
                metric_scores.setdefault(m.metric_name, []).append(m.score)
                metric_passes.setdefault(m.metric_name, []).append(m.passed)

        averages = {k: (sum(v) / len(v) if v else 0.0) for k, v in metric_scores.items()}
        pass_rates = {k: (sum(1 for p in v if p) / len(v) if v else 0.0) for k, v in metric_passes.items()}

        model_name = getattr(self.eval_model, "model_name", None) or str(self.settings.OLLAMA_MODEL)

        return EvaluationReport(
            evaluation_type=eval_type,
            model_name=model_name,
            total_test_cases=total,
            passed_test_cases=passed,
            failed_test_cases=failed,
            overall_pass_rate=pass_rate,
            metric_averages=averages,
            metric_pass_rates=pass_rates,
            case_results=case_results,
        )

    def _print_summary(self, report: EvaluationReport):
        """Prints a clean, concise breakdown of results directly to the console."""
        print("\n" + "=" * 70)
        print(f" Evaluation Summary: {report.evaluation_type}")
        print("=" * 70)
        print(f"Total Cases: {report.total_test_cases} | Passed: {report.passed_test_cases} | Failed: {report.failed_test_cases} | Pass Rate: {report.overall_pass_rate * 100:.1f}%\n")
        
        print("Metric Averages:")
        for m_name, avg in report.metric_averages.items():
            pr = report.metric_pass_rates.get(m_name, 0.0) * 100
            print(f"  • {m_name:35s}: Avg = {avg:.2f} | Pass Rate = {pr:.0f}%")
        
        print("\nCase Results:")
        for c in report.case_results:
            tag = "[PASS]" if c.all_passed else "[FAIL]"
            scores_str = ", ".join([f"{m.metric_name}: {m.score:.2f}" for m in c.metrics])
            print(f"  {tag} {c.test_case_id:25s} -> ({scores_str})")
        print("=" * 70)

    def save_report_json(self, report: EvaluationReport, filename: str) -> Path:
        """Saves evaluation report strictly as a JSON document and prints a summary."""
        self.settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = self.settings.REPORTS_DIR / filename
        data = report.model_dump(mode="json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"\n[OK] Saved JSON report to: {report_path}")
        self._print_summary(report)
        return report_path
