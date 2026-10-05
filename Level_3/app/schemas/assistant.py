from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from app.schemas.order import OrderResponse


class SourceCitation(BaseModel):
    document: str
    section: Optional[str] = None
    excerpt: str
    score: Optional[float] = None


class IntentDetectionResult(BaseModel):
    intent: str = Field(..., description="Classified intent such as order_status, refund, cancellation, etc.")
    needs_order_data: bool = Field(default=False, description="Whether live order data is required")
    needs_rag: bool = Field(default=False, description="Whether RAG knowledge retrieval is required")
    order_id: Optional[str] = Field(default=None, description="Extracted order ID if mentioned or inferred")
    action: Optional[str] = Field(default=None, description="Action requested, e.g., cancel, track")
    reasoning: Optional[str] = Field(default=None, description="Internal routing explanation")


class AssistantResponse(BaseModel):
    answer: str = Field(..., description="Final grounded natural language answer to the user")
    intent: str = Field(default="general_faq", description="Detected intent")
    used_order_api: bool = Field(default=False, description="Whether the Order API was queried")
    used_rag: bool = Field(default=False, description="Whether the RAG system was retrieved")
    order_ids: List[str] = Field(default_factory=list, description="Associated order IDs")
    order_data: Optional[OrderResponse] = Field(default=None, description="Full order details if retrieved")
    sources: List[SourceCitation] = Field(default_factory=list, description="Citations from policy / FAQ documents")
    action_performed: bool = Field(default=False, description="Whether an action (such as cancellation) was performed")
    action_details: Optional[Dict[str, Any]] = Field(default=None, description="Details of the executed action")
    latency_ms: Optional[float] = Field(default=None, description="End-to-end processing time in milliseconds")
