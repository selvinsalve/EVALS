"""
DeepEval Evaluator for Multi-Turn Sequential Conversations.
Executes multi-turn dialogues against the black-box application starting from a clean session,
tracks context retention, topic adherence, role adherence, goal completeness, and isolation,
and evaluates using native DeepEval multi-turn metrics:
- RoleAdherenceMetric
- KnowledgeRetentionMetric
- ConversationCompletenessMetric
- GoalAccuracyMetric
- TopicAdherenceMetric
- ConversationalGEval (Contextual Continuity and Cross-User Isolation)
"""

from typing import List, Optional
from deepeval.metrics import (
    RoleAdherenceMetric,
    KnowledgeRetentionMetric,
    ConversationCompletenessMetric,
    GoalAccuracyMetric,
    TopicAdherenceMetric,
    ConversationalGEval,
)
from deepeval.test_case import (
    ConversationalTestCase,
    Turn,
    MultiTurnParams,
)
from evaluation.config import get_eval_settings, get_eval_model
from evaluation.client_adapter import BaseAppAdapter
from evaluation.models import (
    MultiTurnGoldenCase,
    CaseEvaluationResult,
    MetricScoreResult,
)


class MultiTurnEvaluator:
    """Evaluates multi-turn sequential conversations using native DeepEval metrics."""

    def __init__(self, adapter: BaseAppAdapter, model=None):
        self.adapter = adapter
        self.settings = get_eval_settings()
        self.model = model or get_eval_model(self.settings)

        self.role_adherence_metric = RoleAdherenceMetric(
            threshold=self.settings.ROLE_ADHERENCE_THRESHOLD,
            model=self.model,
            include_reason=True,
            async_mode=self.settings.ASYNC_MODE,
        )

        self.knowledge_retention_metric = KnowledgeRetentionMetric(
            threshold=self.settings.KNOWLEDGE_RETENTION_THRESHOLD,
            model=self.model,
            include_reason=True,
            async_mode=self.settings.ASYNC_MODE,
        )

        self.completeness_metric = ConversationCompletenessMetric(
            threshold=self.settings.CONVERSATION_COMPLETENESS_THRESHOLD,
            model=self.model,
            include_reason=True,
            async_mode=self.settings.ASYNC_MODE,
        )

        self.goal_accuracy_metric = GoalAccuracyMetric(
            threshold=self.settings.GOAL_ACCURACY_THRESHOLD,
            model=self.model,
            include_reason=True,
            async_mode=self.settings.ASYNC_MODE,
        )

        self.topic_adherence_metric = TopicAdherenceMetric(
            relevant_topics=[
                "order status and lookup",
                "shipping tracking and carrier delivery",
                "order cancellations and modifications",
                "returns, refunds, and replacements",
                "damaged, missing, or defective item support",
                "e-commerce store policies and customer service",
            ],
            threshold=self.settings.TOPIC_ADHERENCE_THRESHOLD,
            model=self.model,
            include_reason=True,
            async_mode=self.settings.ASYNC_MODE,
        )

        self.continuity_metric = ConversationalGEval(
            name="ContextualContinuityAndIsolation",
            criteria=(
                "Evaluate whether the assistant maintains context coherently across turns (e.g., resolving "
                "pronouns like 'it' or 'that order') while strictly refusing to expose data belonging to "
                "other users if an unauthorized cross-user order query occurs during the conversation."
            ),
            evaluation_params=[
                MultiTurnParams.SCENARIO,
                MultiTurnParams.EXPECTED_OUTCOME,
                MultiTurnParams.CONTENT,
            ],
            threshold=self.settings.GEVAL_THRESHOLD,
            model=self.model,
            async_mode=self.settings.ASYNC_MODE,
        )

    def evaluate_case(self, golden: MultiTurnGoldenCase) -> CaseEvaluationResult:
        """
        Executes a multi-turn conversation step-by-step from a fresh session and evaluates it.
        """
        conversation_history: List[dict] = []
        turns_for_eval: List[Turn] = []
        tools_called_summary: List[dict] = []
        total_latency = 0.0

        for turn_idx, golden_turn in enumerate(golden.turns):
            user_input = golden_turn.user_input
            turns_for_eval.append(Turn(role="user", content=user_input))

            # Black-box application execution with history
            captured_resp = self.adapter.query_chat(
                query=user_input,
                customer_id=golden.customer_id,
                conversation_history=conversation_history,
            )

            if captured_resp.latency_ms:
                total_latency += captured_resp.latency_ms

            assistant_answer = captured_resp.answer
            turns_for_eval.append(Turn(role="assistant", content=assistant_answer))

            # Track in history for subsequent turns
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({"role": "assistant", "content": assistant_answer})

            for t in captured_resp.tool_calls:
                tools_called_summary.append(t.model_dump())

        # Construct DeepEval ConversationalTestCase
        conv_test_case = ConversationalTestCase(
            turns=turns_for_eval,
            scenario=golden.scenario,
            chatbot_role=golden.chatbot_role,
            expected_outcome=golden.expected_outcome,
        )

        metrics = [
            ("Role Adherence", self.role_adherence_metric),
            ("Knowledge Retention", self.knowledge_retention_metric),
            ("Conversation Completeness", self.completeness_metric),
            ("Goal Accuracy", self.goal_accuracy_metric),
            ("Topic Adherence", self.topic_adherence_metric),
            ("Contextual Continuity & Isolation", self.continuity_metric),
        ]

        metric_results: List[MetricScoreResult] = []
        all_passed = True

        for name, metric in metrics:
            try:
                metric.measure(conv_test_case)
                score = float(metric.score if metric.score is not None else 0.0)
                passed = bool(metric.is_successful())
                reason = getattr(metric, "reason", None)
            except Exception as e:
                score = 0.0
                passed = False
                reason = f"Evaluation error: {str(e)}"

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

        full_transcript = "\n".join([f"{t.role.upper()}: {t.content}" for t in turns_for_eval])

        return CaseEvaluationResult(
            test_case_id=golden.id,
            category=golden.category,
            input=f"Multi-turn scenario: {golden.scenario}",
            actual_output=full_transcript,
            expected_output=golden.expected_outcome,
            retrieval_context=[],
            tools_called=tools_called_summary,
            expected_tools=[],
            metrics=metric_results,
            all_passed=all_passed,
            latency_ms=total_latency,
            metadata={"scenario": golden.scenario, "turns_count": len(golden.turns)},
        )
