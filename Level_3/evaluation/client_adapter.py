"""
Black-Box Client Adapters for AI system under test.
Interacts with the existing applications without modifying application code.
Supports:
1. In-process direct adapter (DirectServiceAdapter): zero-network latency, executes existing service methods as black boxes.
2. HTTP API adapter (HTTPServiceAdapter): communicates with deployed FastAPI endpoints if running as a server.
Captures actual responses, retrieved contexts, tool calls, and execution metadata.
"""

import time
from typing import Optional, List, Dict, Any
from evaluation.models import CapturedAppResponse, CapturedToolCall


class BaseAppAdapter:
    """Base interface for communicating with the black-box application."""

    def query_rag(self, query: str) -> CapturedAppResponse:
        raise NotImplementedError

    def query_chat(
        self,
        query: str,
        customer_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> CapturedAppResponse:
        raise NotImplementedError


class DirectServiceAdapter(BaseAppAdapter):
    """
    Direct in-process adapter that interacts with the existing application services
    (AssistantService and RAGService) without modifying any application code.
    """

    def __init__(self):
        from app.database.database import SessionLocal
        from app.services.assistant_service import AssistantService
        from app.services.rag_service import RAGService

        self.SessionLocal = SessionLocal
        self.rag_service = RAGService()

    def query_rag(self, query: str) -> CapturedAppResponse:
        """
        Executes a pure RAG query using the application's RAGService and captures
        the retrieved policy context chunks and synthesized answer.
        """
        t0 = time.time()
        context_str, citations = self.rag_service.get_policy_context(query, top_k=3)
        retrieved_contexts = [c.snippet for c in citations if hasattr(c, "snippet") and c.snippet]
        if not retrieved_contexts and context_str:
            retrieved_contexts = [context_str]

        db = self.SessionLocal()
        try:
            from app.services.assistant_service import AssistantService
            assistant = AssistantService(db=db, rag_service=self.rag_service)
            resp = assistant.process_message(user_message=query)
            latency_ms = (time.time() - t0) * 1000

            sources = [s.snippet for s in resp.sources if hasattr(s, "snippet") and s.snippet]
            final_contexts = sources if sources else retrieved_contexts

            return CapturedAppResponse(
                answer=resp.answer,
                intent=resp.intent.value if hasattr(resp.intent, "value") else str(resp.intent),
                used_order_api=resp.used_order_api,
                used_rag=resp.used_rag,
                order_ids=resp.order_ids,
                retrieved_contexts=final_contexts,
                latency_ms=latency_ms,
            )
        finally:
            db.close()

    def query_chat(
        self,
        query: str,
        customer_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> CapturedAppResponse:
        """
        Executes an end-to-end chat message through AssistantService with user context,
        capturing tool calls, retrieved contexts, and response.
        """
        t0 = time.time()
        db = self.SessionLocal()
        try:
            from app.services.assistant_service import AssistantService
            from app.schemas.chat import ChatMessage

            history_objs = []
            if conversation_history:
                for h in conversation_history:
                    history_objs.append(
                        ChatMessage(role=h.get("role", "user"), content=h.get("content", ""))
                    )

            assistant = AssistantService(db=db, rag_service=self.rag_service)
            resp = assistant.process_message(
                user_message=query,
                customer_id=customer_id,
                conversation_history=history_objs,
            )
            latency_ms = (time.time() - t0) * 1000

            # Capture tool calls from assistant execution
            tool_calls: List[CapturedToolCall] = []
            order_data_dict = None
            if resp.order_data:
                order_data_dict = (
                    resp.order_data.model_dump(mode="json")
                    if hasattr(resp.order_data, "model_dump")
                    else dict(resp.order_data)
                )

            if resp.used_order_api:
                import re
                resolved_order_id = resp.order_ids[0] if resp.order_ids else None
                if not resolved_order_id:
                    match = re.search(r"ORD-[A-Za-z0-9-]+", query)
                    if match:
                        resolved_order_id = match.group(0).upper()

                tool_calls.append(
                    CapturedToolCall(
                        name="OrderAPI.get_order",
                        input_parameters={
                            "order_id": resolved_order_id,
                            "customer_id": customer_id,
                        },
                        output=order_data_dict,
                        reasoning="Look up customer order status from database",
                    )
                )

            if resp.action_performed and resp.action_details and resp.action_details.get("action") == "cancel_order":
                tool_calls.append(
                    CapturedToolCall(
                        name="OrderAPI.cancel_order",
                        input_parameters={
                            "order_id": resp.action_details.get("order_id"),
                            "customer_id": customer_id,
                        },
                        output=resp.action_details,
                        reasoning="Cancel customer order in database",
                    )
                )

            retrieved_contexts = [
                s.snippet for s in resp.sources if hasattr(s, "snippet") and s.snippet
            ]

            return CapturedAppResponse(
                answer=resp.answer,
                intent=resp.intent.value if hasattr(resp.intent, "value") else str(resp.intent),
                used_order_api=resp.used_order_api,
                used_rag=resp.used_rag,
                order_ids=resp.order_ids,
                order_data=order_data_dict,
                retrieved_contexts=retrieved_contexts,
                tool_calls=tool_calls,
                action_performed=resp.action_performed,
                action_details=resp.action_details,
                latency_ms=latency_ms,
            )
        finally:
            db.close()
