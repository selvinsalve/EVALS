from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from app.evaluation.config import EvaluationConfig
from app.evaluation.models import (
    RAGTestCaseInput,
    RAGEvaluationResult,
    ConversationalEvaluationResult,
    BatchEvaluationSummary,
)
from app.evaluation.rag_evaluator import RAGEvaluator
from app.evaluation.conversational_evaluator import ConversationalEvaluator
from app.evaluation.runner import EvaluationRunner
from app.schemas.chat import ChatMessage
from app.utils.logging import logger

router = APIRouter(prefix="/api/eval", tags=["Evaluation"])


@router.get("/metrics")
def get_evaluation_metrics_info():
    """List all supported RAG and Conversational evaluation metrics and current thresholds."""
    config = EvaluationConfig()
    return {
        "judge_model": {
            "provider": config.llm_provider,
            "ollama_model": config.ollama_model,
            "ollama_base_url": config.ollama_base_url,
        },
        "rag_metrics": {
            "faithfulness": {"threshold": config.faithfulness_threshold, "description": "Checks factual grounding in retrieval_context"},
            "answer_relevancy": {"threshold": config.answer_relevancy_threshold, "description": "Checks if output addresses user query"},
            "contextual_relevancy": {"threshold": config.contextual_relevancy_threshold, "description": "Checks relevance of retrieved chunks to query"},
            "contextual_precision": {"threshold": config.contextual_precision_threshold, "description": "Evaluates ranking of relevant context chunks"},
            "contextual_recall": {"threshold": config.contextual_recall_threshold, "description": "Evaluates coverage of expected facts in retrieval context"},
        },
        "conversational_metrics": {
            "turn_relevancy": {"threshold": config.turn_relevancy_threshold, "description": "Evaluates turn-by-turn relevance"},
            "turn_faithfulness": {"threshold": config.turn_faithfulness_threshold, "description": "Evaluates turn-by-turn context grounding"},
            "role_adherence": {"threshold": config.role_adherence_threshold, "description": "Checks persona consistency"},
            "conversation_completeness": {"threshold": config.conversation_completeness_threshold, "description": "Checks if user goal was resolved"},
            "conversational_coherence": {"threshold": config.conversational_geval_threshold, "description": "Evaluates multi-turn logic and empathy"},
            "knowledge_retention": {"threshold": config.knowledge_retention_threshold, "description": "Evaluates recall of facts across turns"},
        },
    }


@router.post("/rag", response_model=RAGEvaluationResult)
def evaluate_rag_case(
    payload: RAGTestCaseInput,
    metrics: Optional[List[str]] = Query(None, description="Optional subset of metric names to evaluate"),
) -> RAGEvaluationResult:
    """
    Evaluate a single RAG interaction (input, actual_output, retrieval_context, expected_output).
    Returns scores, thresholds, pass/fail status, and reasons.
    """
    evaluator = RAGEvaluator()
    try:
        return evaluator.evaluate(
            input=payload.input,
            actual_output=payload.actual_output,
            retrieval_context=payload.retrieval_context,
            expected_output=payload.expected_output,
            context=payload.context,
            test_case_id=payload.id,
            metric_names=metrics,
        )
    except Exception as e:
        logger.error("RAG evaluation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"RAG evaluation error: {str(e)}")


@router.post("/conversational", response_model=ConversationalEvaluationResult)
def evaluate_conversational_session(
    chat_history: List[ChatMessage],
    scenario: Optional[str] = Query(None, description="Contextual scenario of the session"),
    session_id: Optional[str] = Query(None, description="Session ID"),
    metrics: Optional[List[str]] = Query(None, description="Optional metric names to evaluate"),
) -> ConversationalEvaluationResult:
    """
    Evaluate a multi-turn chat session using DeepEval conversational metrics.
    """
    evaluator = ConversationalEvaluator()
    try:
        return evaluator.evaluate_session(
            chat_history=chat_history,
            scenario=scenario,
            session_id=session_id,
            metric_names=metrics,
        )
    except Exception as e:
        logger.error("Conversational evaluation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Conversational evaluation error: {str(e)}")
