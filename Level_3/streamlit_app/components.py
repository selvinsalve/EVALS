import streamlit as st
from typing import List, Optional, Dict, Any


def render_header():
    """Render the application hero header."""
    st.markdown(
        """
        <div class="app-header">
            <h1 class="app-title">AI Order Assistant</h1>
            <p class="app-subtitle">Ask about orders, delivery, returns, refunds, cancellations, and store policies.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_latency(latency_ms: Optional[float]):
    """Render a subtle, minimalist latency indicator for the user."""
    if not latency_ms:
        return
    time_str = f"{latency_ms / 1000.0:.2f}s" if latency_ms >= 1000 else f"{latency_ms:.0f}ms"
    st.markdown(
        f'<div style="font-size: 0.72rem; color: #64748b; margin-top: 6px; font-family: monospace;">⚡ {time_str}</div>',
        unsafe_allow_html=True,
    )


def render_badges(used_order_api: bool, used_rag: bool, intent: Optional[str] = None):
    """Optional badges (kept as harmless no-op for backward compatibility)."""
    pass


def render_order_card(order: Dict[str, Any]):
    """Render a structured e-commerce order card using native Streamlit containers."""
    if not order:
        return

    status = order.get("status", "UNKNOWN")
    order_id = order.get("order_id", "N/A")
    
    if status in ("PLACED", "CONFIRMED", "PROCESSING"):
        carrier = order.get("carrier") or "Assigned at dispatch"
        tracking = order.get("tracking_number") or "Pending dispatch"
    elif status == "CANCELLED":
        carrier = order.get("carrier") or "None"
        tracking = order.get("tracking_number") or "Cancelled"
    else:
        carrier = order.get("carrier") or "Carrier pending"
        tracking = order.get("tracking_number") or "N/A"

    est_date = order.get("estimated_delivery_date")
    est_date_str = est_date[:10] if est_date else "Pending"
    total = order.get("total_amount", 0.0)
    currency = order.get("currency", "USD")
    shipping_addr = order.get("shipping_address", "N/A")
    items = order.get("items", [])

    with st.container(border=True):
        col_hdr_left, col_hdr_right = st.columns([3, 1])
        with col_hdr_left:
            st.markdown(f"### 📦 Order `{order_id}`")
        with col_hdr_right:
            if status in ("SHIPPED", "DELIVERED"):
                st.success(f"● {status}")
            elif status in ("DELAYED", "RETURN_REQUESTED"):
                st.warning(f"● {status}")
            elif status == "CANCELLED":
                st.error(f"● {status}")
            else:
                st.info(f"● {status}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Carrier", carrier)
        c2.metric("Tracking", tracking)
        c3.metric("Est. Delivery", est_date_str)
        c4.metric("Total", f"${total:.2f} {currency}")

        shipment = order.get("shipment")
        if shipment and shipment.get("current_location"):
            st.caption(f"📍 **Current Location:** {shipment.get('current_location')}")
        st.caption(f"🏠 **Destination:** {shipping_addr}")

        if items:
            with st.expander("🛒 Ordered Line Items", expanded=True):
                for item in items:
                    st.markdown(f"- **{item.get('product_name')}** &times; {item.get('quantity')} &mdash; `${item.get('unit_price', 0):.2f}`")


def render_sources(sources: List[Dict[str, Any]]):
    """Render expandable source policy citations."""
    if not sources:
        return

    with st.expander(f"📖 Store Policy References ({len(sources)})", expanded=False):
        for idx, src in enumerate(sources):
            doc = src.get("document", "Policy Document")
            section = src.get("section", "General")
            excerpt = src.get("excerpt", "")
            score = src.get("score")
            score_text = f" *(relevance: {score})*" if score else ""

            st.markdown(f"**📄 {doc}** &mdash; *Section: {section}*{score_text}")
            st.caption(excerpt)
            if idx < len(sources) - 1:
                st.divider()


def render_request_details(*args, **kwargs):
    """Removed observability expander for clean consumer UI."""
    pass
