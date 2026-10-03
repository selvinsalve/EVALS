import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Union

from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    BaseMetric,
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
)

from app.evaluation.config import EvaluationConfig, get_eval_model
from app.evaluation.models import (
    MetricScore,
    RAGTestCaseInput,
    RAGEvaluationResult,
    BatchEvaluationSummary,
)
from app.utils.logging import logger


class RAGEvaluator:
    """
    Reusable evaluation service for RAG retrieval and generation quality.
    
    Integrates DeepEval RAG metrics:
      1. Faithfulness (checks if actual_output is factually grounded in retrieval_context)
      2. Answer Relevance (checks if actual_output directly addresses the input query)
      3. Contextual Relevancy (evaluates if retrieved chunks are relevant to input)
      4. Contextual Precision (evaluates if the most relevant chunks are ranked at the top)
      5. Contextual Recall (evaluates if retrieval_context covers all facts in expected_output)
    """

    def __init__(
        self,
        config: Optional[EvaluationConfig] = None,
        model: Optional[Any] = None,
    ):
        self.config = config or EvaluationConfig()
        self.model = model or get_eval_model(self.config)
        self._init_metrics()

    def _init_metrics(self) -> None:
        """Instantiate configured DeepEval RAG metrics."""
        self.faithfulness_metric = FaithfulnessMetric(
            threshold=self.config.faithfulness_threshold,
            model=self.model,
            include_reason=self.config.include_reason,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.answer_relevancy_metric = AnswerRelevancyMetric(
            threshold=self.config.answer_relevancy_threshold,
            model=self.model,
            include_reason=self.config.include_reason,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.contextual_relevancy_metric = ContextualRelevancyMetric(
            threshold=self.config.contextual_relevancy_threshold,
            model=self.model,
            include_reason=self.config.include_reason,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.contextual_precision_metric = ContextualPrecisionMetric(
            threshold=self.config.contextual_precision_threshold,
            model=self.model,
            include_reason=self.config.include_reason,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.contextual_recall_metric = ContextualRecallMetric(
            threshold=self.config.contextual_recall_threshold,
            model=self.model,
            include_reason=self.config.include_reason,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.metrics_map: Dict[str, BaseMetric] = {
            "faithfulness": self.faithfulness_metric,
            "answer_relevancy": self.answer_relevancy_metric,
            "contextual_relevancy": self.contextual_relevancy_metric,
            "contextual_precision": self.contextual_precision_metric,
            "contextual_recall": self.contextual_recall_metric,
        }

    def get_metrics_for_case(
        self,
        has_expected_output: bool,
        metric_names: Optional[List[str]] = None,
    ) -> List[BaseMetric]:
        """
        Return the list of metrics to run.
        Filters out Contextual Recall & Precision if expected_output is absent.
        """
        selected_names = [m.lower().strip() for m in (metric_names or list(self.metrics_map.keys()))]
        metrics: List[BaseMetric] = []

        for name in selected_names:
            if name in self.metrics_map:
                # Precision and Recall require expected_output
                if name in ("contextual_precision", "contextual_recall") and not has_expected_output:
                    logger.warning(
                        "Skipping '%s' because expected_output was not provided for this test case.", name
                    )
                    continue
                metrics.append(self.metrics_map[name])

        return metrics

    @staticmethod
    def create_test_case(
        input: str,
        actual_output: str,
        retrieval_context: List[str],
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LLMTestCase:
        """Create a validated DeepEval LLMTestCase."""
        clean_retrieval_ctx = [str(c).strip() for c in retrieval_context if str(c).strip()]
        if not clean_retrieval_ctx:
            clean_retrieval_ctx = ["No retrieval context available."]

        return LLMTestCase(
            input=input,
            actual_output=actual_output,
            expected_output=expected_output,
            retrieval_context=clean_retrieval_ctx,
            context=context,
            name=name,
            metadata=metadata,
        )

    def evaluate(
        self,
        input: str,
        actual_output: str,
        retrieval_context: List[str],
        expected_output: Optional[str] = None,
        context: Optional[List[str]] = None,
        test_case_id: Optional[str] = None,
        metric_names: Optional[List[str]] = None,
    ) -> RAGEvaluationResult:
        """
        Reusable evaluation function evaluating retrieval and generation quality for a single turn.
        
        Args:
            input: The user query
            actual_output: The generated response from the RAG / Assistant service
            retrieval_context: List of retrieved context text chunks
            expected_output: Optional ground truth response (from golden dataset)
            context: Optional reference context
            test_case_id: Optional test identifier
            metric_names: Optional list of metrics to run (e.g. ['faithfulness', 'answer_relevancy'])
            
        Returns:
            RAGEvaluationResult with individual metric scores, reasons, and overall pass/fail status.
        """
        test_case = self.create_test_case(
            input=input,
            actual_output=actual_output,
            retrieval_context=retrieval_context,
            expected_output=expected_output,
            context=context,
            name=test_case_id,
        )
        return self.evaluate_test_case(test_case=test_case, metric_names=metric_names)

    def evaluate_test_case(
        self,
        test_case: LLMTestCase,
        metric_names: Optional[List[str]] = None,
    ) -> RAGEvaluationResult:
        """Evaluate an existing LLMTestCase and return structured results."""
        start_time = time.time()
        has_expected_output = bool(test_case.expected_output and str(test_case.expected_output).strip())
        metrics_to_run = self.get_metrics_for_case(has_expected_output, metric_names)

        results_dict: Dict[str, MetricScore] = {}
        all_passed = True
        scores: List[float] = []

        logger.info("Running %d RAG metrics for test case: '%s'...", len(metrics_to_run), test_case.input[:60])

        for metric in metrics_to_run:
            metric_name = metric.__class__.__name__
            try:
                metric.measure(test_case)
                score = round(float(metric.score or 0.0), 3)
                passed = bool(metric.is_successful())
                reason = getattr(metric, "reason", None)
                breakdown = getattr(metric, "score_breakdown", None)

                results_dict[metric_name] = MetricScore(
                    metric_name=metric_name,
                    score=score,
                    threshold=metric.threshold,
                    passed=passed,
                    reason=reason,
                    score_breakdown=breakdown if isinstance(breakdown, dict) else None,
                )
                scores.append(score)
                if not passed:
                    all_passed = False

            except Exception as e:
                logger.error("Metric %s failed with exception: %s", metric_name, e)
                results_dict[metric_name] = MetricScore(
                    metric_name=metric_name,
                    score=0.0,
                    threshold=metric.threshold,
                    passed=False,
                    reason=f"Evaluation failed with error: {str(e)}",
                    error=str(e),
                )
                all_passed = False

        avg_score = round(sum(scores) / len(scores), 3) if scores else 0.0
        elapsed = round(time.time() - start_time, 2)

        return RAGEvaluationResult(
            test_case_id=test_case.name or getattr(test_case, "id", None),
            input=test_case.input,
            actual_output=test_case.actual_output,
            expected_output=test_case.expected_output,
            retrieval_context=test_case.retrieval_context or [],
            metrics=results_dict,
            overall_passed=all_passed,
            average_score=avg_score,
            execution_time_seconds=elapsed,
        )

    def evaluate_batch(
        self,
        test_cases: List[Union[LLMTestCase, RAGTestCaseInput, Dict[str, Any]]],
        metric_names: Optional[List[str]] = None,
    ) -> BatchEvaluationSummary:
        """
        Evaluate a batch of RAG test cases and generate an aggregated summary report.
        """
        start_time = time.time()
        run_id = f"rag_eval_{uuid.uuid4().hex[:8]}"
        results: List[RAGEvaluationResult] = []

        total = len(test_cases)
        passed_count = 0
        metric_score_accum: Dict[str, List[float]] = {}

        for idx, item in enumerate(test_cases, 1):
            if isinstance(item, LLMTestCase):
                tc = item
            elif isinstance(item, RAGTestCaseInput):
                tc = self.create_test_case(
                    input=item.input,
                    actual_output=item.actual_output,
                    retrieval_context=item.retrieval_context,
                    expected_output=item.expected_output,
                    context=item.context,
                    name=item.id or f"case_{idx}",
                    metadata=item.metadata,
                )
            elif isinstance(item, dict):
                tc = self.create_test_case(
                    input=item.get("input", ""),
                    actual_output=item.get("actual_output", ""),
                    retrieval_context=item.get("retrieval_context", []),
                    expected_output=item.get("expected_output"),
                    context=item.get("context"),
                    name=item.get("id") or item.get("name") or f"case_{idx}",
                )
            else:
                continue

            res = self.evaluate_test_case(tc, metric_names=metric_names)
            results.append(res)
            if res.overall_passed:
                passed_count += 1

            for m_name, m_res in res.metrics.items():
                metric_score_accum.setdefault(m_name, []).append(m_res.score)

        elapsed = round(time.time() - start_time, 2)
        metric_averages = {
            m: round(sum(scores) / len(scores), 3) for m, scores in metric_score_accum.items() if scores
        }
        pass_rate = round((passed_count / total * 100.0), 2) if total else 0.0

        model_name = getattr(self.model, "model_name", None) or getattr(self.model, "model", str(self.model))

        return BatchEvaluationSummary(
            run_id=run_id,
            evaluation_type="RAG",
            timestamp=datetime.now(timezone.utc).isoformat(),
            model_used=str(model_name),
            total_test_cases=total,
            passed_test_cases=passed_count,
            failed_test_cases=total - passed_count,
            pass_rate=pass_rate,
            metric_averages=metric_averages,
            results=results,
            total_execution_time_seconds=elapsed,
        )

    def assert_test(
        self,
        input: str,
        actual_output: str,
        retrieval_context: List[str],
        expected_output: Optional[str] = None,
        metric_names: Optional[List[str]] = None,
    ) -> None:
        """
        Execute DeepEval's native assert_test() on a RAG test case.
        Designed for direct use in Pytest test functions.
        """
        test_case = self.create_test_case(
            input=input,
            actual_output=actual_output,
            retrieval_context=retrieval_context,
            expected_output=expected_output,
        )
        has_expected_output = bool(expected_output and str(expected_output).strip())
        metrics_to_run = self.get_metrics_for_case(has_expected_output, metric_names)
        assert_test(test_case=test_case, metrics=metrics_to_run, run_async=self.config.async_mode)
