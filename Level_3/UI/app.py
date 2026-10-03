import sys
import importlib
from pathlib import Path
import httpx
import streamlit as st

# Ensure root directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import streamlit_app.styles as styles
import streamlit_app.components as components
import app.config as config_module
importlib.reload(styles)
importlib.reload(components)
importlib.reload(config_module)
if hasattr(config_module.get_settings, "cache_clear"):
    config_module.get_settings.cache_clear()

from app.config import get_settings
from streamlit_app.styles import CUSTOM_CSS
from streamlit_app.components import (
    render_order_card,
    render_sources,
    render_latency,
)

settings = config_module.get_settings()

st.set_page_config(
    page_title="AI Order Assistant",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Apply custom styles
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

if "customer_id" not in st.session_state:
    st.session_state.customer_id = "CUS-001"

if "suggested_input" not in st.session_state:
    st.session_state.suggested_input = None


def check_api_health():
    """Verify backend API health status."""
    try:
        resp = httpx.get(f"{settings.BACKEND_URL}/health", timeout=2.0)
        if resp.status_code == 200:
            return True, resp.json()
    except Exception:
        pass
    return False, None


def check_ollama_health():
    """Verify Ollama local server availability."""
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=1.5)
        if resp.status_code == 200:
            return True, resp.json()
    except Exception:
        pass
    return False, None


def call_assistant_api(message: str, customer_id: str, history: list, llm_provider: str = "ollama"):
    """Send query to the Assistant endpoint (via HTTP with direct service fallback)."""
    # Try calling FastAPI backend over HTTP
    try:
        payload = {
            "message": message,
            "customer_id": customer_id,
            "conversation_history": [
                {"role": m["role"], "content": m["content"]}
                for m in history[-6:]
            ],
            "llm_provider": llm_provider,
        }
        resp = httpx.post(f"{settings.BACKEND_URL}/assistant/chat", json=payload, timeout=180.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass

    # Direct fallback: use local service instance
    from app.database.database import SessionLocal
    from app.services.assistant_service import AssistantService
    from app.schemas.chat import ChatMessage

    db = SessionLocal()
    try:
        service = AssistantService(db=db, llm_provider=llm_provider)
        conv_hist = [
            ChatMessage(role=m["role"], content=m["content"])
            for m in history[-6:]
        ]
        result = service.process_message(
            user_message=message,
            customer_id=customer_id,
            conversation_history=conv_hist,
            llm_provider=llm_provider,
        )
        return result.model_dump()
    finally:
        db.close()


# Default LLM provider
if "llm_provider" not in st.session_state:
    st.session_state.llm_provider = "ollama"


# ---------------- TOP DASHBOARD HEADER & ACCOUNT SELECTOR ----------------
with st.container():
    col_brand, col_account, col_action = st.columns([5, 4, 2], vertical_alignment="center")
    with col_brand:
        st.markdown(
            """
            <div style="padding: 2px 0;">
                <h1 style="font-size: 1.85rem; font-weight: 700; margin: 0; color: #f8fafc; letter-spacing: -0.02em;">
                    🛍️ AI Order Assistant
                </h1>
                <p style="font-size: 0.92rem; color: #94a3b8; margin: 3px 0 0 0;">
                    Instant answers for your orders, tracking, refunds, returns & store policies
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_account:
        customers = [
            ("CUS-001", "Sarah Connor"),
            ("CUS-002", "Alex Mercer"),
            ("CUS-003", "Elena Fisher"),
            ("CUS-004", "Marcus Vance"),
            ("CUS-005", "Diana Prince"),
            ("CUS-006", "James Holden"),
            ("CUS-007", "Naomi Nagata"),
            ("CUS-008", "Arthur Dent"),
            ("CUS-009", "Tess Coleman"),
            ("CUS-010", "Victor Stone"),
        ]
        customer_options = {cid: f"👤 {name} ({cid})" for cid, name in customers}
        cur_idx = list(customer_options.keys()).index(st.session_state.customer_id) if st.session_state.customer_id in customer_options else 0
        selected_cid = st.selectbox(
            "Account Switcher",
            options=list(customer_options.keys()),
            format_func=lambda x: customer_options[x],
            index=cur_idx,
            label_visibility="collapsed",
            help="Switch customer account to view your specific orders",
        )
        if selected_cid != st.session_state.customer_id:
            st.session_state.customer_id = selected_cid
            st.rerun()

    with col_action:
        if st.button("🗑️ Clear Chat", use_container_width=True, help="Clear conversation history"):
            st.session_state.messages = []
            st.rerun()

st.divider()


def get_customer_suggestions(customer_id: str) -> list[str]:
    """Dynamically generate suggested questions strictly tailored to the active customer."""
    from app.database.database import SessionLocal
    from app.services.order_service import OrderService

    base_policy_questions = [
        "What is the refund policy?",
        "Can I return an opened item?",
        "How do I cancel an order?",
    ]

    personalized = ["Where is my latest order?"]

    _db = SessionLocal()
    try:
        service = OrderService(_db)
        orders = service.get_customer_orders(customer_id)

        # Check for actionable orders belonging to THIS customer only
        cancellable = next((o for o in orders if o.status in ["PLACED", "CONFIRMED", "PROCESSING"]), None)
        in_transit = next((o for o in orders if o.status in ["SHIPPED", "IN_TRANSIT", "OUT_FOR_DELIVERY"]), None)
        delivered = next((o for o in orders if o.status == "DELIVERED"), None)

        if cancellable:
            personalized.append(f"Can I cancel {cancellable.order_id}?")
        if in_transit:
            personalized.append(f"Where is order {in_transit.order_id}?")
        elif orders and len(orders) > 0 and not cancellable:
            personalized.append(f"What is the status of {orders[0].order_id}?")

        if delivered:
            personalized.append(f"Can I return items from {delivered.order_id}?")
        elif len(orders) > 1:
            used_ids = {getattr(cancellable, "order_id", None), getattr(in_transit, "order_id", None)}
            other_order = next((o for o in orders if o.order_id not in used_ids), None)
            if other_order:
                personalized.append(f"Track my order {other_order.order_id}")
    except Exception:
        pass
    finally:
        _db.close()

    # Fill remainder up to 6 with general policy questions
    all_suggestions = []
    for q in personalized + base_policy_questions:
        if q not in all_suggestions:
            all_suggestions.append(q)

    fallback_faqs = [
        "What happens if my package is lost or missing?",
        "How long do refunds take to process?",
        "Do you offer free return shipping?",
    ]
    for fq in fallback_faqs:
        if len(all_suggestions) >= 6:
            break
        if fq not in all_suggestions:
            all_suggestions.append(fq)

    return all_suggestions[:6]


# Suggested Questions
st.markdown("##### 💡 Suggested Questions")
suggestions = get_customer_suggestions(st.session_state.customer_id)
suggested_cols = st.columns(3)

for idx, q_text in enumerate(suggestions):
    col = suggested_cols[idx % 3]
    if col.button(q_text, key=f"sugg_{idx}", use_container_width=True):
        st.session_state.suggested_input = q_text
        st.rerun()

st.markdown("<br/>", unsafe_allow_html=True)

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Display structured cards and badges for assistant responses
        if msg["role"] == "assistant":
            if msg.get("order_data"):
                render_order_card(msg["order_data"])

            if msg.get("sources"):
                render_sources(msg["sources"])

            render_latency(msg.get("latency_ms"))

# Handle Input
prompt_to_process = None
if st.session_state.suggested_input:
    prompt_to_process = st.session_state.suggested_input
    st.session_state.suggested_input = None
else:
    user_prompt = st.chat_input("Ask about orders, tracking, refunds, returns, or policies...")
    if user_prompt:
        prompt_to_process = user_prompt

if prompt_to_process:
    # 1. Append user message
    st.session_state.messages.append({"role": "user", "content": prompt_to_process})
    with st.chat_message("user"):
        st.markdown(prompt_to_process)

    # 2. Get assistant response
    with st.chat_message("assistant"):
        with st.spinner("Processing request with Order API & RAG..."):
            resp = call_assistant_api(
                message=prompt_to_process,
                customer_id=st.session_state.customer_id,
                history=st.session_state.messages[:-1],
                llm_provider=st.session_state.get("llm_provider", "ollama"),
            )

            answer = resp.get("answer", "I'm sorry, I could not process your request.")
            st.markdown(answer)

            if resp.get("order_data"):
                render_order_card(resp["order_data"])

            if resp.get("sources"):
                render_sources(resp.get("sources", []))

            render_latency(resp.get("latency_ms"))

            # Store in session state
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "intent": resp.get("intent"),
                "used_order_api": resp.get("used_order_api", False),
                "used_rag": resp.get("used_rag", False),
                "order_data": resp.get("order_data"),
                "sources": resp.get("sources", []),
                "action_performed": resp.get("action_performed", False),
                "action_details": resp.get("action_details"),
                "latency_ms": resp.get("latency_ms"),
            })
