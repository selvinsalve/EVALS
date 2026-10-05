import pytest
from app.database.database import SessionLocal
from app.database.seed import init_db, seed_data
from app.services.assistant_service import AssistantService
from app.services.llm_service import DemoLLMService


@pytest.fixture(scope="module", autouse=True)
def init_data():
    init_db()
    seed_data()


from app.database.models import Order


@pytest.fixture
def assistant():
    db = SessionLocal()
    # Reset ORD-1003 to PROCESSING so cancellation tests are idempotent
    ord_1003 = db.query(Order).filter(Order.order_id == "ORD-1003").first()
    if ord_1003:
        ord_1003.status = "PROCESSING"
        ord_1003.cancellation_allowed = True
        ord_1003.payment_status = "PAID"
        db.commit()

    svc = AssistantService(db=db, llm_service=DemoLLMService())
    yield svc
    db.close()


def test_order_status_requires_order_api(assistant):
    """'Where is ORD-1001?' should detect order_status and use Order API."""
    response = assistant.process_message("Where is ORD-1001?", customer_id="CUS-001")
    assert response.used_order_api is True
    assert "ORD-1001" in response.order_ids
    assert "SHIPPED" in response.answer or "shipped" in response.answer
    assert response.order_data is not None


def test_policy_question_requires_rag(assistant):
    """'What is your return policy?' should require RAG and not query live order data."""
    response = assistant.process_message("What is your return policy?")
    assert response.used_rag is True
    assert "30" in response.answer  # 30-day window
    assert len(response.sources) >= 1 or "return" in response.answer.lower()


def test_delayed_order_refund_requires_both(assistant):
    """'My order ORD-1001 is delayed. Can I get a refund?' requires both Order API + RAG."""
    response = assistant.process_message(
        "My order ORD-1001 is delayed. Can I get a refund?",
        customer_id="CUS-001",
    )
    assert response.used_order_api is True
    assert response.used_rag is True
    assert "ORD-1001" in response.answer
    assert "refund" in response.answer.lower()


def test_cancellation_action_permitted(assistant):
    """'Cancel ORD-1003' should invoke cancellation and record action execution."""
    response = assistant.process_message("Cancel ORD-1003", customer_id="CUS-001")
    assert response.used_order_api is True
    assert response.action_performed is True
    assert "successfully cancelled" in response.answer


def test_cancellation_denied_for_shipped(assistant):
    """'Cancel ORD-1001' should deny cancellation because the order is SHIPPED."""
    response = assistant.process_message("Cancel ORD-1001", customer_id="CUS-001")
    assert response.used_order_api is True
    assert response.action_performed is False
    assert "cannot be cancelled" in response.answer


def test_cross_customer_order_access_blocked(assistant):
    """Customer CUS-002 should NOT be permitted to access CUS-001's order ORD-1001."""
    response = assistant.process_message("Where is ORD-1001?", customer_id="CUS-002")
    assert response.order_data is None
    assert response.order_ids == []
    assert "not associated with your account" in response.answer.lower() or "privacy" in response.answer.lower()


def test_cross_customer_cancellation_blocked(assistant):
    """Customer CUS-002 should NOT be permitted to cancel CUS-001's order ORD-1003."""
    response = assistant.process_message("Cancel ORD-1003", customer_id="CUS-002")
    assert response.action_performed is False
    assert response.order_data is None
    assert "not associated with your account" in response.answer.lower() or "privacy" in response.answer.lower()


def test_greeting_guardrail_does_not_use_rag(assistant):
    """Greetings like 'how are you' or 'hello' must not trigger RAG or policy documents."""
    for greeting in ["how are you", "hello", "hi there"]:
        response = assistant.process_message(greeting)
        assert response.used_rag is False
        assert response.used_order_api is False
        assert len(response.sources) == 0
        assert response.intent == "greeting"
        assert "ai order assistant" in response.answer.lower()


def test_out_of_scope_weather_guardrail_does_not_use_rag(assistant):
    """Out-of-scope queries like weather or jokes must trigger guardrail notice without RAG."""
    for query in ["what is the weather today", "tell me a joke", "write a python function"]:
        response = assistant.process_message(query)
        assert response.used_rag is False
        assert response.used_order_api is False
        assert len(response.sources) == 0
        assert response.intent == "out_of_scope"
        assert "guardrail notice" in response.answer.lower() or "specialized" in response.answer.lower()
