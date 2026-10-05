from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.services.assistant_service import AssistantService
from app.schemas.chat import ChatRequest
from app.schemas.assistant import AssistantResponse

router = APIRouter(prefix="", tags=["Assistant"])


@router.post("/assistant/chat", response_model=AssistantResponse)
@router.post("/chat", response_model=AssistantResponse)
def chat_with_assistant(request: ChatRequest, db: Session = Depends(get_db)) -> AssistantResponse:
    """
    Main endpoint for conversing with the AI Order Assistant.
    Orchestrates intent detection, Order API lookup, RAG retrieval, and grounded response synthesis.
    """
    service = AssistantService(db=db, llm_provider=request.llm_provider)
    response = service.process_message(
        user_message=request.message,
        customer_id=request.customer_id,
        conversation_history=request.conversation_history,
        llm_provider=request.llm_provider,
    )
    return response
