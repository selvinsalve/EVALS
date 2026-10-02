import re
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import httpx
from app.config import get_settings
from app.schemas.assistant import IntentDetectionResult
from app.utils.logging import logger

settings = get_settings()


class BaseLLMService(ABC):
    """Abstract interface for LLM orchestration and response generation."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate response given a system prompt and user context prompt."""
        pass

    @abstractmethod
    def classify_intent(
        self,
        query: str,
        recent_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentDetectionResult:
        """Analyze query and conversation history to determine routing and entities."""
        pass


class OllamaLLMService(BaseLLMService):
    """LLM implementation utilizing local Ollama server (e.g. Qwen 2.5)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or settings.OLLAMA_MODEL
        logger.info("Initialized Ollama LLM Service at %s with model '%s'", self.base_url, self.model)

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        options: Dict[str, Any] = {"temperature": 0.2}
        if max_tokens:
            options["num_predict"] = max_tokens

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if json_mode:
            payload["format"] = "json"

        try:
            with httpx.Client(timeout=180.0) as client:
                resp = client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error("Ollama API call failed: %s", e)
            raise

    def classify_intent(
        self,
        query: str,
        recent_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentDetectionResult:
        """Classify user intent using local Qwen model with fallback to rule engine."""
        history_context = ""
        if recent_history:
            history_context = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent_history[-4:]])

        system_prompt = (
            "You are an intent router for an e-commerce customer support AI. "
            "Analyze the user query and recent history to identify requirements.\n"
            "Respond strictly in valid JSON with this exact schema:\n"
            "{\n"
            '  "intent": "order_status" | "order_tracking" | "order_details" | "latest_order" | "cancellation" | '
            '"refund" | "return" | "damaged_order" | "delayed_order" | "refund_for_delayed_order" | "delivery" | "shipping" | "payment" | "greeting" | "out_of_scope" | "general_faq",\n'
            '  "needs_order_data": boolean,\n'
            '  "needs_rag": boolean,\n'
            '  "order_id": string or null,\n'
            '  "action": string or null,\n'
            '  "reasoning": string\n'
            "}\n"
            "Rules:\n"
            "- If the query is a greeting, pleasantry, or introductory question (e.g., 'hello', 'hi', 'how are you', 'who are you', 'good morning'), set intent='greeting', needs_order_data=false, needs_rag=false, order_id=null.\n"
            "- If the query is out-of-scope or unrelated to e-commerce, orders, shipments, returns, cancellations, or store policies (e.g., 'what is the weather today', 'tell me a joke', 'who is the president', 'write code', math), set intent='out_of_scope', needs_order_data=false, needs_rag=false, order_id=null.\n"
            "- If the query asks for general policies (e.g. 'What is the refund policy?', 'return policy', 'shipping charges', 'payment methods'), "
            "set needs_order_data=false, needs_rag=true, order_id=null, EVEN IF a previous order was mentioned in history!\n"
            "- Only bind order_id from history if the user refers to it contextually (e.g., 'when will it arrive?', 'can I cancel it?').\n"
            "- If the user asks about a refund for a delayed order (e.g. 'My order ORD-1001 is delayed. Can I get a refund?'), "
            "set BOTH needs_order_data=true and needs_rag=true.\n"
            "- If user asks to cancel an order, set action='cancel' and needs_order_data=true."
        )

        user_prompt = f"Recent History:\n{history_context or 'None'}\n\nUser Query: {query}"

        try:
            raw_json = self.generate(user_prompt, system_prompt, json_mode=True, max_tokens=150)
            data = json.loads(raw_json)
            return IntentDetectionResult(
                intent=data.get("intent", "general_faq"),
                needs_order_data=data.get("needs_order_data", False),
                needs_rag=data.get("needs_rag", False),
                order_id=data.get("order_id"),
                action=data.get("action"),
                reasoning=data.get("reasoning", "Ollama Qwen classified"),
            )
        except Exception as e:
            logger.warning("Ollama intent classification failed (%s), using rule-based fallback.", e)
            demo_fallback = DemoLLMService()
            return demo_fallback.classify_intent(query, recent_history)


class OpenAILLMService(BaseLLMService):
    """LLM implementation utilizing OpenAI API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:
            logger.error("Failed to initialize OpenAI client: %s", e)
            self.client = None

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
    ) -> str:
        if not self.client:
            raise RuntimeError("OpenAI client is not initialized. Please verify OPENAI_API_KEY.")

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            response_format = {"type": "json_object"} if json_mode else None

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format,
                max_tokens=max_tokens,
                temperature=0.1,
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI API call failed: %s", e)
            raise

    def classify_intent(
        self,
        query: str,
        recent_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentDetectionResult:
        history_context = ""
        if recent_history:
            history_context = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent_history[-4:]])

        system_prompt = (
            "You are an intent router for an e-commerce AI assistant. "
            "Analyze the user query and recent history to identify requirements.\n"
            "Respond strictly with valid JSON with this schema:\n"
            "{\n"
            '  "intent": string (one of: order_status, order_tracking, order_details, latest_order, cancellation, '
            'refund, return, damaged_order, delayed_order, refund_for_delayed_order, delivery, shipping, payment, greeting, out_of_scope, general_faq, unknown),\n'
            '  "needs_order_data": boolean,\n'
            '  "needs_rag": boolean,\n'
            '  "order_id": string or null (e.g. "ORD-1001"),\n'
            '  "action": string or null (e.g. "cancel" if requesting cancellation),\n'
            '  "reasoning": string\n'
            "}\n"
            "Rules:\n"
            "- If the query is a greeting, pleasantry, or introductory question (e.g., 'hello', 'hi', 'how are you', 'who are you', 'good morning'), set intent='greeting', needs_order_data=false, needs_rag=false, order_id=null.\n"
            "- If the query is out-of-scope or unrelated to e-commerce, orders, shipments, returns, cancellations, or store policies (e.g., 'what is the weather today', 'tell me a joke', 'who is the president', 'write code', math), set intent='out_of_scope', needs_order_data=false, needs_rag=false, order_id=null.\n"
            "- If the query is a general store policy question (e.g., 'What is the refund policy?', 'What is your return policy?', 'shipping rates'), "
            "set needs_order_data=false, needs_rag=true, order_id=null, EVEN IF a previous order was mentioned in history!\n"
            "- Only use order_id from history if the user specifically refers to it (e.g., 'when will it arrive?').\n"
            "- If the user asks about an order status, tracking, or latest order, set needs_order_data=true.\n"
            "- If the user asks about a refund for a delayed order, set BOTH needs_order_data=true AND needs_rag=true."
        )

        user_prompt = f"Recent History:\n{history_context}\n\nUser Query: {query}"

        try:
            raw_json = self.generate(user_prompt, system_prompt, json_mode=True)
            data = json.loads(raw_json)
            return IntentDetectionResult(
                intent=data.get("intent", "general_faq"),
                needs_order_data=data.get("needs_order_data", False),
                needs_rag=data.get("needs_rag", False),
                order_id=data.get("order_id"),
                action=data.get("action"),
                reasoning=data.get("reasoning", "OpenAI classified"),
            )
        except Exception as e:
            logger.warning("OpenAI classification failed, falling back to Demo classifier: %s", e)
            demo_fallback = DemoLLMService()
            return demo_fallback.classify_intent(query, recent_history)


class DemoLLMService(BaseLLMService):
    """
    Deterministic, offline AI reasoning layer.
    Allows complete local testing and demonstration without needing an OpenAI API key or external LLM.
    Follows all grounding rules strictly.
    """

    def classify_intent(
        self,
        query: str,
        recent_history: Optional[List[Dict[str, str]]] = None,
    ) -> IntentDetectionResult:
        q = query.lower().strip()

        # 1. Check if user explicitly provided an Order ID in this query
        order_id_match = re.search(r"\b(ORD-\d{4})\b", query, re.IGNORECASE)
        explicit_order_id = order_id_match.group(1).upper() if order_id_match else None

        # 2. Check for general policy questions vs order-specific queries
        is_general_refund = bool(re.search(r"\b(what is (the|your)|tell me about the) refund policy\b", q)) or q == "refund policy"
        is_general_return = bool(re.search(r"\b(what is (the|your)|tell me about the) return policy\b", q)) or q == "return policy" or "what is the return window" in q
        is_shipping_rate_query = bool(re.search(r"\b(shipping (charge|cost|rate|fee|methods)|how much is shipping|delivery rates)\b", q))
        is_payment_query = bool(re.search(r"\b(payment|credit card|apple pay|paypal|klarna|supported payment)\b", q))
        is_general_faq = bool(re.search(r"\b(contact|support hours|customer service hours|speak to human|talk to human)\b", q))

        # Check if query contains an anaphoric / contextual pronoun referencing an order ("it", "this order", "my order", "cancel it", "when will it arrive")
        has_anaphoric_order_ref = bool(re.search(r"\b(it|this|that|my order|the order|this order|that order|for it|its)\b", q))

        # Infer order_id from history ONLY if explicitly referenced or query is anaphoric and not a general policy
        order_id = explicit_order_id
        is_pure_policy = is_general_refund or is_general_return or is_shipping_rate_query or is_payment_query or is_general_faq

        if not order_id and recent_history and has_anaphoric_order_ref and not is_pure_policy:
            for msg in reversed(recent_history):
                hist_match = re.search(r"\b(ORD-\d{4})\b", msg.get("content", ""), re.IGNORECASE)
                if hist_match:
                    order_id = hist_match.group(1).upper()
                    break

        # Check intent types
        is_cancel_action = bool(re.search(r"\b(cancel|cancellation)\b", q))
        is_refund_query = bool(re.search(r"\b(refund|money back|reimburse)\b", q))
        is_return_query = bool(re.search(r"\b(return|send back|exchange)\b", q))
        is_delayed_query = bool(re.search(r"\b(delay|delayed|late|taking so long)\b", q))
        is_damage_query = bool(re.search(r"\b(damage|damaged|broken|defective|crushed)\b", q))
        is_missing_query = bool(re.search(r"\b(missing|lost|didn't arrive|haven't received|not arrived)\b", q))
        is_address_query = bool(re.search(r"\b(change (my )?(delivery )?address|update address)\b", q))
        is_latest_order = bool(re.search(r"\b(latest|recent|last)\s+order\b", q))
        is_status_or_tracking = bool(re.search(r"\b(where is|status|track|tracking|when will.*arrive|arrival)\b", q))

        # Guardrail Check 1: Greetings & Assistant Capabilities (No Order API, No RAG)
        is_greeting = bool(
            re.search(
                r"^(hi|hello|hey|howdy|hola|greetings|good\s+(morning|afternoon|evening)|how\s+are\s+you|how's\s+it\s+going|what's\s+up|who\s+are\s+you|what\s+can\s+you\s+do)\b",
                q,
            )
        ) or q in ("hi", "hello", "hey", "how are you", "how are you?", "who are you?", "who are you", "what can you do?", "what can you do", "help")
        if is_greeting and not explicit_order_id and not any(kw in q for kw in ("order", "refund", "return", "cancel", "ship", "deliver", "track")):
            return IntentDetectionResult(
                intent="greeting",
                needs_order_data=False,
                needs_rag=False,
                order_id=None,
                reasoning="User greeting or capability inquiry handled by conversational guardrail.",
            )

        # Guardrail Check 2: Out of Scope / Irrelevant queries (No Order API, No RAG)
        is_weather = bool(re.search(r"\b(weather|temperature|forecast|rain|snow|humidity|climate|sunny|cloudy)\b", q))
        is_coding = bool(re.search(r"\b(write\s+(a\s+)?(python|code|script|program|sql|function)|debug\s+code)\b", q))
        is_general_knowledge = bool(re.search(r"\b(capital\s+of|president\s+of|prime\s+minister|who\s+is\s+(the\s+)?(president|elon|trump|biden)|who\s+won|score\s+of|tell\s+me\s+a\s+joke|joke|meaning\s+of\s+life|recipe\s+for|how\s+to\s+cook)\b", q))
        is_out_of_scope = (is_weather or is_coding or is_general_knowledge) and not any(
            kw in q for kw in ("order", "item", "product", "refund", "return", "shipping", "delivery", "track", "cancel", "store", "policy")
        )

        if is_out_of_scope and not explicit_order_id:
            return IntentDetectionResult(
                intent="out_of_scope",
                needs_order_data=False,
                needs_rag=False,
                order_id=None,
                reasoning="Query is out of scope / external domain. Blocked by guardrail.",
            )

        # Priority 1: Pure Policy Questions (RAG only, NO order data)
        if is_pure_policy and not explicit_order_id:
            if is_general_refund:
                return IntentDetectionResult(intent="refund", needs_order_data=False, needs_rag=True, order_id=None)
            if is_general_return:
                return IntentDetectionResult(intent="return", needs_order_data=False, needs_rag=True, order_id=None)
            if is_shipping_rate_query:
                return IntentDetectionResult(intent="shipping", needs_order_data=False, needs_rag=True, order_id=None)
            if is_payment_query:
                return IntentDetectionResult(intent="payment", needs_order_data=False, needs_rag=True, order_id=None)
            if is_general_faq:
                return IntentDetectionResult(intent="general_faq", needs_order_data=False, needs_rag=True, order_id=None)

        # Priority 2: Delayed Order + Refund ("My order ORD-1001 is delayed. Can I get a refund?")
        if (is_delayed_query and is_refund_query) or (order_id and is_delayed_query):
            return IntentDetectionResult(
                intent="refund_for_delayed_order",
                needs_order_data=True,
                needs_rag=True,
                order_id=order_id,
                reasoning="Requires both live order status and refund policy retrieval.",
            )

        # Priority 3: Cancellation request or inquiry
        if is_cancel_action:
            needs_order = bool(order_id or is_latest_order or has_anaphoric_order_ref)
            return IntentDetectionResult(
                intent="cancellation",
                needs_order_data=needs_order,
                needs_rag=True,
                order_id=order_id,
                action="cancel" if ("cancel" in q and order_id) else None,
                reasoning="Cancellation intent requires checking policy and live cancellation_allowed if order specified.",
            )

        # Priority 4: Damaged order inquiry
        if is_damage_query:
            return IntentDetectionResult(
                intent="damaged_order",
                needs_order_data=bool(order_id or is_latest_order),
                needs_rag=True,
                order_id=order_id,
                reasoning="Requires damaged order resolution policy and order details if specified.",
            )

        # Priority 5: Missing / Delivered but lost
        if is_missing_query:
            return IntentDetectionResult(
                intent="missing_order",
                needs_order_data=bool(order_id or is_latest_order),
                needs_rag=True,
                order_id=order_id,
                reasoning="Requires delivery policy for lost parcels and order tracking if specified.",
            )

        # Priority 6: Pure status / tracking / latest order
        if is_latest_order:
            return IntentDetectionResult(
                intent="latest_order",
                needs_order_data=True,
                needs_rag=False,
                order_id=None,
                reasoning="Requires fetching latest order for active customer.",
            )

        if is_status_or_tracking or (order_id and not (is_refund_query or is_return_query)):
            return IntentDetectionResult(
                intent="order_status",
                needs_order_data=True,
                needs_rag=False,
                order_id=order_id,
                reasoning="Order status/tracking lookup requires Order API.",
            )

        # Priority 7: Return policy
        if is_return_query:
            return IntentDetectionResult(
                intent="return",
                needs_order_data=bool(explicit_order_id or (order_id and has_anaphoric_order_ref)),
                needs_rag=True,
                order_id=order_id if (explicit_order_id or has_anaphoric_order_ref) else None,
                reasoning="Return policy question requires RAG.",
            )

        # Priority 8: Refund policy
        if is_refund_query:
            return IntentDetectionResult(
                intent="refund",
                needs_order_data=bool(explicit_order_id or (order_id and has_anaphoric_order_ref)),
                needs_rag=True,
                order_id=order_id if (explicit_order_id or has_anaphoric_order_ref) else None,
                reasoning="Refund policy question requires RAG.",
            )

        # Priority 9: Address changes
        if is_address_query:
            return IntentDetectionResult(
                intent="delivery",
                needs_order_data=bool(order_id or is_latest_order),
                needs_rag=True,
                order_id=order_id,
                reasoning="Address modification rules governed by shipping policy and order status.",
            )

        # Fallback: check if the query contains any e-commerce / policy domain keywords
        ecommerce_keywords = (
            "order", "item", "product", "refund", "return", "ship", "deliver", "track",
            "cancel", "pay", "fee", "cost", "price", "warranty", "package", "parcel",
            "box", "receipt", "account", "address", "policy", "faq", "support", "contact"
        )
        if not any(kw in q for kw in ecommerce_keywords) and not explicit_order_id:
            return IntentDetectionResult(
                intent="out_of_scope",
                needs_order_data=False,
                needs_rag=False,
                order_id=None,
                reasoning="Query does not contain e-commerce or policy keywords. Routed to out-of-scope guardrail.",
            )

        # Default FAQ fallback
        return IntentDetectionResult(
            intent="general_faq",
            needs_order_data=bool(explicit_order_id),
            needs_rag=True,
            order_id=explicit_order_id,
            reasoning="Default fallback to general RAG FAQ.",
        )

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        json_mode: bool = False,
        max_tokens: Optional[int] = None,
    ) -> str:
        return "Deterministic demo response generated via AssistantService synthesis rules."


def get_llm_service(provider_override: Optional[str] = None) -> BaseLLMService:
    """Factory function returning the configured LLM implementation."""
    provider = (provider_override or settings.LLM_PROVIDER).lower().strip()

    if provider == "ollama":
        try:
            # Check if Ollama server is reachable
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                if res.status_code == 200:
                    logger.info("Using local Ollama LLM Service (%s at %s).", settings.OLLAMA_MODEL, settings.OLLAMA_BASE_URL)
                    return OllamaLLMService()
        except Exception as e:
            logger.warning("Ollama check failed (%s), falling back to Demo service.", e)

    if provider == "openai" and not settings.DEMO_MODE and settings.OPENAI_API_KEY:
        logger.info("Using OpenAI LLM Service (%s).", settings.OPENAI_MODEL)
        return OpenAILLMService()

    logger.info("Using Demo/Mock LLM Service (deterministic local reasoning).")
    return DemoLLMService()
