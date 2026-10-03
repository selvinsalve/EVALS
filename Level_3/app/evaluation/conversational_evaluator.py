import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Union

from deepeval import assert_test
from deepeval.test_case import ConversationalTestCase, Turn, MultiTurnParams
from deepeval.metrics import (
    BaseConversationalMetric,
    TurnRelevancyMetric,
    TurnFaithfulnessMetric,
    RoleAdherenceMetric,
    ConversationCompletenessMetric,
    KnowledgeRetentionMetric,
    ConversationalGEval,
)

from app.schemas.chat import ChatMessage
from app.evaluation.config import EvaluationConfig, get_eval_model
from app.evaluation.models import (
    MetricScore,
    TurnEvaluationDetail,
    ConversationalEvaluationResult,
    BatchEvaluationSummary,
)
from app.utils.logging import logger


class ConversationalEvaluator:
    """
    Evaluation service for multi-turn chat sessions and conversational quality.
    
    Integrates DeepEval multi-turn conversational metrics:
      1. Turn Relevancy (evaluates if each assistant turn directly relates to user requests and context)
      2. Turn Faithfulness (evaluates if assistant claims are strictly grounded in retrieval_context for that turn)
      3. Conversation Completeness (checks if the user's intent was resolved across the multi-turn exchange)
      4. Role Adherence (ensures the assistant maintains its designated customer service persona)
      5. Conversational G-Eval (evaluates overall coherence, empathy, and domain grounding)
      6. Knowledge Retention (ensures information provided in earlier turns is retained in subsequent turns)
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
        """Instantiate configured DeepEval conversational metrics."""
        self.turn_relevancy_metric = TurnRelevancyMetric(
            threshold=self.config.turn_relevancy_threshold,
            model=self.model,
            include_reason=self.config.include_reason,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.turn_faithfulness_metric = TurnFaithfulnessMetric(
            threshold=self.config.turn_faithfulness_threshold,
            model=self.model,
            include_reason=self.config.include_reason,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.role_adherence_metric = RoleAdherenceMetric(
            threshold=self.config.role_adherence_threshold,
            model=self.model,
            include_reason=self.config.include_reason,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.conversation_completeness_metric = ConversationCompletenessMetric(
            threshold=self.config.conversation_completeness_threshold,
            model=self.model,
            include_reason=self.config.include_reason,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.knowledge_retention_metric = KnowledgeRetentionMetric(
            threshold=self.config.knowledge_retention_threshold,
            model=self.model,
            include_reason=self.config.include_reason,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.coherence_geval = ConversationalGEval(
            name="Conversational Coherence & Grounding",
            criteria=(
                "Evaluate whether the assistant maintains a coherent, professional, and helpful conversation. "
                "The assistant must not hallucinate false order details, must strictly reference policy context, "
                "and must follow up logically on questions asked in previous turns."
            ),
            evaluation_params=[MultiTurnParams.CONTENT, MultiTurnParams.ROLE],
            model=self.model,
            threshold=self.config.conversational_geval_threshold,
            async_mode=self.config.async_mode,
            strict_mode=self.config.strict_mode,
            verbose_mode=self.config.verbose_mode,
        )

        self.metrics_map: Dict[str, BaseConversationalMetric] = {
            "turn_relevancy": self.turn_relevancy_metric,
            "turn_faithfulness": self.turn_faithfulness_metric,
            "role_adherence": self.role_adherence_metric,
            "conversation_completeness": self.conversation_completeness_metric,
            "knowledge_retention": self.knowledge_retention_metric,
            "conversational_coherence": self.coherence_geval,
        }

    def build_test_case(
        self,
        chat_history: List[Union[ChatMessage, Turn, Dict[str, Any]]],
        scenario: Optional[str] = None,
        session_id: Optional[str] = None,
        chatbot_role: Optional[str] = None,
        expected_outcome: Optional[str] = None,
    ) -> ConversationalTestCase:
        """
        Convert diverse chat history inputs into a standardized DeepEval ConversationalTestCase.
        
        Supports:
          - List of ChatMessage objects from app.schemas.chat
          - List of DeepEval Turn objects
          - List of dictionaries with role and content keys
        """
        turns: List[Turn] = []

        for item in chat_history:
            if isinstance(item, Turn):
                turns.append(item)
            elif isinstance(item, ChatMessage):
                turns.append(Turn(role=item.role, content=item.content))
            elif isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content", "")
                retrieval_ctx = item.get("retrieval_context")
                if retrieval_ctx and isinstance(retrieval_ctx, list):
                    clean_ctx = [str(c) for c in retrieval_ctx]
                elif retrieval_ctx:
                    clean_ctx = [str(retrieval_ctx)]
                else:
                    clean_ctx = None

                turns.append(
                    Turn(
                        role=role,
                        content=content,
                        retrieval_context=clean_ctx,
                        tools_called=item.get("tools_called"),
                        metadata=item.get("metadata"),
                    )
                )

        return ConversationalTestCase(
            turns=turns,
            chatbot_role=chatbot_role or self.config.chatbot_role,
            scenario=scenario or "Customer support inquiry for e-commerce orders and store policies.",
            name=session_id or f"session_{uuid.uuid4().hex[:8]}",
            expected_outcome=expected_outcome,
        )

    def evaluate_session(
        self,
        chat_history: List[Union[ChatMessage, Turn, Dict[str, Any]]],
        scenario: Optional[str] = None,
        session_id: Optional[str] = None,
        expected_outcome: Optional[str] = None,
        metric_names: Optional[List[str]] = None,
    ) -> ConversationalEvaluationResult:
        """
        Ingest a multi-turn chat history log and evaluate session quality against conversational metrics.
        """
        test_case = self.build_test_case(
            chat_history=chat_history,
            scenario=scenario,
            session_id=session_id,
            expected_outcome=expected_outcome,
        )
        return self.evaluate_test_case(test_case=test_case, metric_names=metric_names)

    def evaluate_test_case(
        self,
        test_case: ConversationalTestCase,
        metric_names: Optional[List[str]] = None,
    ) -> ConversationalEvaluationResult:
        """Evaluate an existing ConversationalTestCase and return structured results."""
        start_time = time.time()
        selected_names = [m.lower().strip() for m in (metric_names or list(self.metrics_map.keys()))]

        # Check if any turns have retrieval_context; if not, skip turn_faithfulness
        has_retrieval_context = any(
            bool(t.retrieval_context) for t in test_case.turns if t.role == "assistant"
        )

        results_dict: Dict[str, MetricScore] = {}
        all_passed = True
        scores: List[float] = []

        logger.info(
            "Evaluating conversational session '%s' with %d turns across %d metrics...",
            test_case.name, len(test_case.turns), len(selected_names)
        )

        for name in selected_names:
            if name not in self.metrics_map:
                continue

            if name == "turn_faithfulness" and not has_retrieval_context:
                logger.info("Skipping 'turn_faithfulness': no assistant turns contained retrieval_context.")
                continue

            metric = self.metrics_map[name]
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
                logger.error("Conversational metric %s failed with exception: %s", metric_name, e)
                results_dict[metric_name] = MetricScore(
                    metric_name=metric_name,
                    score=0.0,
                    threshold=metric.threshold,
                    passed=False,
                    reason=f"Evaluation failed with error: {str(e)}",
                    error=str(e),
                )
                all_passed = False

        # Build turn detail snapshots
        turn_details = [
            TurnEvaluationDetail(
                turn_index=idx,
                role=turn.role,
                content=turn.content,
                retrieval_context=turn.retrieval_context,
            )
            for idx, turn in enumerate(test_case.turns, 1)
        ]

        avg_score = round(sum(scores) / len(scores), 3) if scores else 0.0
        elapsed = round(time.time() - start_time, 2)

        return ConversationalEvaluationResult(
            session_id=test_case.name,
            scenario=test_case.scenario,
            chatbot_role=test_case.chatbot_role,
            total_turns=len(test_case.turns),
            metrics=results_dict,
            turn_details=turn_details,
            overall_passed=all_passed,
            average_score=avg_score,
            execution_time_seconds=elapsed,
        )

    def evaluate_batch_sessions(
        self,
        sessions: List[Dict[str, Any]],
        metric_names: Optional[List[str]] = None,
    ) -> BatchEvaluationSummary:
        """
        Evaluate multiple chat session logs in batch.
        
        Args:
            sessions: List of dicts, each with keys 'session_id', 'scenario', and 'turns'
        """
        start_time = time.time()
        run_id = f"conv_eval_{uuid.uuid4().hex[:8]}"
        results: List[ConversationalEvaluationResult] = []

        total = len(sessions)
        passed_count = 0
        metric_score_accum: Dict[str, List[float]] = {}

        for idx, sess in enumerate(sessions, 1):
            sess_id = sess.get("session_id") or f"sess_{idx}"
            scenario = sess.get("scenario")
            turns = sess.get("turns", [])
            expected_outcome = sess.get("expected_outcome")

            res = self.evaluate_session(
                chat_history=turns,
                scenario=scenario,
                session_id=sess_id,
                expected_outcome=expected_outcome,
                metric_names=metric_names,
            )
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
            evaluation_type="Conversational",
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
        test_case: ConversationalTestCase,
        metric_names: Optional[List[str]] = None,
    ) -> None:
        """Execute DeepEval's native assert_test() on a ConversationalTestCase for Pytest."""
        selected_names = [m.lower().strip() for m in (metric_names or list(self.metrics_map.keys()))]
        metrics = [self.metrics_map[m] for m in selected_names if m in self.metrics_map]
        assert_test(test_case=test_case, metrics=metrics, run_async=self.config.async_mode)
