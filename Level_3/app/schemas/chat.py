from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's query or message")
    customer_id: Optional[str] = Field(default=None, description="Current authenticated or demo customer ID")
    conversation_history: List[ChatMessage] = Field(default_factory=list, description="Recent conversation messages for context")
    llm_provider: Optional[str] = Field(default=None, description="LLM provider: 'ollama', 'openai', or 'demo'")
