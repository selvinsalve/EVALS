"""
DeepEval Evaluator for RAG Application.
Evaluates RAG pipeline outputs using DeepEval metrics:
- Answer Relevancy (AnswerRelevancyMetric)
- Faithfulness (FaithfulnessMetric)
- Contextual Precision (ContextualPrecisionMetric)
- Contextual Recall (ContextualRecallMetric)
- Contextual Relevancy (ContextualRelevancyMetric)
"""

from typing import List, Optional
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
)
from deepeval.test_case import LLMTestCase
from evaluation.config import get_eval_settings, get_eval_model
from evaluation.models import (
    RAGGoldenCase,
    CapturedAppResponse,
    CaseEvaluationResult,
    MetricScoreResult,
)


class RAGEvaluator:
    """Evaluates RAG retrieval and generation using native DeepEval metrics."""

    def __init__(self, model=None):
        self.settings = get_eval_settings()
        self.model = model or get_eval_model(self.settings)

        self.answer_relevancy_metric = AnswerRelevancyMetric(
            threshold=self.settings.ANSWER_RELEVANCY_THRESHOLD,
            model=self.model,
            include_reason=True,
            async_mode=self.settings.ASYNC_MODE,
        )
        self.faithfulness_metric = FaithfulnessMetric(
            threshold=self.settings.FAITHFULNESS_THRESHOLD,
            model=self.model,
            include_reason=True,
            async_mode=self.settings.ASYNC_MODE,
        )
        self.contextual_precision_metric = ContextualPrecisionMetric(
            threshold=self.settings.CONTEXTUAL_PRECISION_THRESHOLD,
            model=self.model,
            include_reason=True,
            async_mode=self.settings.ASYNC_MODE,
        )
        self.contextual_recall_metric = ContextualRecallMetric(
            threshold=self.settings.CONTEXTUAL_RECALL_THRESHOLD,
            model=self.model,
            include_reason=True,
            async_mode=self.settings.ASYNC_MODE,
        )
        self.contextual_relevancy_metric = ContextualRelevancyMetric(
            threshold=self.settings.CONTEXTUAL_RELEVANCY_THRESHOLD,
            model=self.model,
            include_reason=True,
            async_mode=self.settings.ASYNC_MODE,
        )

    def evaluate_case(
        self,
        golden: RAGGoldenCase,
        app_response: CapturedAppResponse,
    ) -> CaseEvaluationResult:
        """
        Runs all 5 DeepEval RAG metrics on the captured response against golden ground truth.
        """
        # Retrieval context: use captured context from application or fallback to golden context
        retrieval_context = (
            app_response.retrieved_contexts
            if app_response.retrieved_contexts
            else golden.context
        )

        test_case = LLMTestCase(
            input=golden.input,
            actual_output=app_response.answer,
            expected_output=golden.expected_output,
            retrieval_context=retrieval_context,
            context=golden.context,
        )

        metric_results: List[MetricScoreResult] = []
        metrics = [
            ("Answer Relevancy", self.answer_relevancy_metric),
            ("Faithfulness", self.faithfulness_metric),
            ("Contextual Precision", self.contextual_precision_metric),
            ("Contextual Recall", self.contextual_recall_metric),
            ("Contextual Relevancy", self.contextual_relevancy_metric),
        ]

        all_passed = True
        for name, metric in metrics:
            try:
                metric.measure(test_case)
                score = float(metric.score if metric.score is not None else 0.0)
                passed = bool(metric.is_successful())
                reason = getattr(metric, "reason", None)
            except Exception as e:
                score = 0.0
                passed = False
                reason = f"Metric evaluation error: {str(e)}"

            if not passed:
                all_passed = False

            metric_results.append(
                MetricScoreResult(
                    metric_name=name,
                    score=score,
                    threshold=float(metric.threshold),
                    passed=passed,
                    reason=reason,
                )
            )

        return CaseEvaluationResult(
            test_case_id=golden.id,
            category=golden.category,
            input=golden.input,
            actual_output=app_response.answer,
            expected_output=golden.expected_output,
            retrieval_context=retrieval_context,
            tools_called=[],
            expected_tools=[],
            metrics=metric_results,
            all_passed=all_passed,
            latency_ms=app_response.latency_ms,
            metadata={"difficulty": golden.difficulty, "source_document": golden.source_document},
        )
