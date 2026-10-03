"""
Pytest Suite for DeepEval RAG and Multi-Turn Conversational Evaluations.
Demonstrates both programmatic test runs and DeepEval's native assert_test().
"""
import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase, ConversationalTestCase, Turn
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    RoleAdherenceMetric,
    ConversationCompletenessMetric,
)

from app.evaluation.config import EvaluationConfig, get_eval_model
from app.evaluation.rag_evaluator import RAGEvaluator
from app.evaluation.conversational_evaluator import ConversationalEvaluator


@pytest.fixture(scope="session")
def eval_config():
    """Provides test evaluation configuration."""
    return EvaluationConfig(
        faithfulness_threshold=0.6,
        answer_relevancy_threshold=0.6,
        contextual_relevancy_threshold=0.5,
        contextual_precision_threshold=0.5,
        contextual_recall_threshold=0.5,
        role_adherence_threshold=0.6,
        async_mode=False,
    )


@pytest.fixture(scope="session")
def eval_model(eval_config):
    """Provides shared evaluation model (Ollama or OpenAI)."""
    return get_eval_model(eval_config)


class TestRAGEvaluation:
    """Test suite for RAG retrieval and generation metrics."""

    def test_reusable_rag_evaluator_service(self, eval_config, eval_model):
        """Verify the reusable RAGEvaluator service executes and returns structured results."""
        evaluator = RAGEvaluator(config=eval_config, model=eval_model)

        result = evaluator.evaluate(
            input="Can I cancel an order that is already shipped?",
            actual_output="No, once an order is in SHIPPED status, cancellation is not possible. You must wait for delivery to return it.",
            expected_output="Orders in SHIPPED status cannot be cancelled once handed over to the carrier.",
            retrieval_context=[
                "Cancellation is strictly impossible once the package has been handed over to the carrier (FedEx, UPS, USPS, DHL). In this scenario allow delivery and initiate a return."
            ],
            test_case_id="pytest_rag_001",
            metric_names=["faithfulness", "answer_relevancy"],
        )

        assert result.test_case_id == "pytest_rag_001"
        assert "FaithfulnessMetric" in result.metrics
        assert "AnswerRelevancyMetric" in result.metrics
        assert result.metrics["FaithfulnessMetric"].score >= 0.0
        assert result.metrics["AnswerRelevancyMetric"].score >= 0.0
        assert result.execution_time_seconds > 0.0

    def test_rag_assert_test_faithfulness(self, eval_config, eval_model):
        """Demonstrate native assert_test() usage with FaithfulnessMetric."""
        test_case = LLMTestCase(
            input="What is the standard return window?",
            actual_output="The return window is 30 days from the confirmed delivery date.",
            expected_output="Customers may request a return within 30 days of delivery.",
            retrieval_context=[
                "Customers may request a return within 30 days of the confirmed delivery date. Returns initiated after 30 days cannot be accepted."
            ],
        )

        faithfulness = FaithfulnessMetric(
            threshold=eval_config.faithfulness_threshold,
            model=eval_model,
            async_mode=False,
        )

        # Uses DeepEval assert_test for pytest integration
        assert_test(test_case=test_case, metrics=[faithfulness], run_async=False)

    def test_contextual_retrieval_metrics(self, eval_config, eval_model):
        """Evaluate Contextual Relevancy, Precision, and Recall."""
        evaluator = RAGEvaluator(config=eval_config, model=eval_model)

        result = evaluator.evaluate(
            input="Who pays for return shipping on defective items?",
            actual_output="If the return is due to store error or defective merchandise, the store provides a free prepaid return shipping label.",
            expected_output="The store provides a prepaid return shipping label at no cost for defective items.",
            retrieval_context=[
                "If the return is due to our error (defective, damaged, or incorrect item), we provide a prepaid return shipping label.",
                "For buyer's remorse, the customer is responsible for the $6.99 return shipping cost.",
            ],
            metric_names=["contextual_relevancy", "contextual_precision", "contextual_recall"],
        )

        assert len(result.metrics) == 3
        for m_name, score_obj in result.metrics.items():
            assert score_obj.score is not None
            assert score_obj.score >= 0.0


class TestConversationalEvaluation:
    """Test suite for Multi-Turn Conversational metrics and test cases."""

    def test_conversational_evaluator_session(self, eval_config, eval_model):
        """Verify ConversationalEvaluator processes chat history into ConversationalTestCase."""
        evaluator = ConversationalEvaluator(config=eval_config, model=eval_model)

        chat_history = [
            {"role": "user", "content": "Hi, I have a question about my order ORD-1002."},
            {"role": "assistant", "content": "Hello! I can help you with order ORD-1002. What would you like to know?"},
            {"role": "user", "content": "How long do I have to return an item?"},
            {
                "role": "assistant",
                "content": "You can return items within 30 days of the delivery date, provided they are unused and in original packaging.",
                "retrieval_context": ["Customers may request a return within 30 days of the confirmed delivery date."],
            },
        ]

        result = evaluator.evaluate_session(
            chat_history=chat_history,
            scenario="Customer inquiring about order return eligibility",
            session_id="pytest_conv_001",
            metric_names=["role_adherence", "turn_relevancy"],
        )

        assert result.session_id == "pytest_conv_001"
        assert result.total_turns == 4
        assert "RoleAdherenceMetric" in result.metrics
        assert "TurnRelevancyMetric" in result.metrics
        assert result.metrics["RoleAdherenceMetric"].score >= 0.0

    def test_conversational_assert_test(self, eval_config, eval_model):
        """Demonstrate assert_test() on a ConversationalTestCase."""
        conv_case = ConversationalTestCase(
            chatbot_role=eval_config.chatbot_role,
            turns=[
                Turn(role="user", content="Can I track my package?"),
                Turn(role="assistant", content="Yes, please provide your order ID and I will check your tracking details immediately."),
            ],
        )

        role_metric = RoleAdherenceMetric(
            threshold=eval_config.role_adherence_threshold,
            model=eval_model,
            async_mode=False,
        )

        assert_test(test_case=conv_case, metrics=[role_metric], run_async=False)
