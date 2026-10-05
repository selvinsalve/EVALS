"""
Data models for golden datasets, evaluation test cases, captured execution artifacts,
and evaluation reports.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Golden Dataset Models
# ---------------------------------------------------------------------------

class RAGGoldenCase(BaseModel):
    id: str
    input: str
    expected_output: str
    context: List[str]
    source_document: Optional[str] = None
    category: str = "general"
    difficulty: str = "medium"  # easy, medium, hard, adversarial, negative
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DBGoldenCase(BaseModel):
    id: str
    input: str
    customer_id: Optional[str] = None
    expected_output: str
    expected_order_id: Optional[str] = None
    expected_status: Optional[str] = None
    expected_tools: List[Dict[str, Any]] = Field(default_factory=list)
    category: str = "order_tracking"
    is_cross_user_attempt: bool = False
    is_nonexistent: bool = False
    is_ambiguous: bool = False
    difficulty: str = "medium"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MultiTurnGoldenTurn(BaseModel):
    user_input: str
    expected_assistant_response: str
    expected_tools: List[Dict[str, Any]] = Field(default_factory=list)
    reference_context: List[str] = Field(default_factory=list)
    turn_intent: Optional[str] = None


class MultiTurnGoldenCase(BaseModel):
    id: str
    scenario: str
    customer_id: Optional[str] = None
    chatbot_role: str = "Professional e-commerce AI Order Assistant"
    expected_outcome: str
    turns: List[MultiTurnGoldenTurn]
    category: str = "multi_turn_inquiry"
    difficulty: str = "medium"
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Captured Black-Box Application Response
# ---------------------------------------------------------------------------

class CapturedToolCall(BaseModel):
    name: str
    input_parameters: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Any] = None
    reasoning: Optional[str] = None


class CapturedAppResponse(BaseModel):
    answer: str
    intent: Optional[str] = None
    used_order_api: bool = False
    used_rag: bool = False
    order_ids: List[str] = Field(default_factory=list)
    order_data: Optional[Dict[str, Any]] = None
    retrieved_contexts: List[str] = Field(default_factory=list)
    tool_calls: List[CapturedToolCall] = Field(default_factory=list)
    action_performed: bool = False
    action_details: Optional[Dict[str, Any]] = None
    latency_ms: Optional[float] = None
    raw_response: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Evaluation Results & Reporting Models (Strictly JSON)
# ---------------------------------------------------------------------------

class MetricScoreResult(BaseModel):
    metric_name: str
    score: float
    threshold: float
    passed: bool
    reason: Optional[str] = None
    strict_mode: bool = False


class CaseEvaluationResult(BaseModel):
    test_case_id: str
    category: str
    input: str
    actual_output: str
    expected_output: Optional[str] = None
    retrieval_context: List[str] = Field(default_factory=list)
    tools_called: List[Dict[str, Any]] = Field(default_factory=list)
    expected_tools: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: List[MetricScoreResult] = Field(default_factory=list)
    all_passed: bool = True
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvaluationReport(BaseModel):
    evaluation_type: str  # "RAG", "DATABASE_CHATBOT", "MULTI_TURN"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    model_name: str
    total_test_cases: int
    passed_test_cases: int
    failed_test_cases: int
    overall_pass_rate: float
    metric_averages: Dict[str, float] = Field(default_factory=dict)
    metric_pass_rates: Dict[str, float] = Field(default_factory=dict)
    case_results: List[CaseEvaluationResult] = Field(default_factory=list)
