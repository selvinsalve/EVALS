import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.seed import init_db, seed_data


@pytest.fixture(scope="module", autouse=True)
def setup_app_db():
    """Ensure database and seed data are initialized."""
    init_db()
    seed_data()


@pytest.fixture(scope="module")
def client():
    """Create a FastAPI test client."""
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    """Test the /health endpoint."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "database" in data


def test_get_order_success(client):
    """Test /orders/{order_id} with existing order."""
    resp = client.get("/orders/ORD-1001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_id"] == "ORD-1001"
    assert data["status"] == "SHIPPED"
    assert data["carrier"] == "FedEx"
    assert len(data["items"]) >= 1


def test_get_order_not_found(client):
    """Test /orders/{order_id} with non-existent order."""
    resp = client.get("/orders/ORD-NONEXISTENT")
    assert resp.status_code == 404


def test_get_customer_orders(client):
    """Test /customers/{customer_id}/orders."""
    resp = client.get("/customers/CUS-001/orders")
    assert resp.status_code == 200
    orders = resp.json()
    assert isinstance(orders, list)
    assert len(orders) >= 1


def test_get_order_status(client):
    """Test /orders/{order_id}/status."""
    resp = client.get("/orders/ORD-1001/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_id"] == "ORD-1001"
    assert data["status"] == "SHIPPED"


def test_get_order_tracking(client):
    """Test /orders/{order_id}/tracking."""
    resp = client.get("/orders/ORD-1001/tracking")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tracking_number"] == "FDX-99482110"
    assert data["carrier"] == "FedEx"


def test_cancel_shipped_order_rejected(client):
    """Test that attempting to cancel a shipped order returns 400 Bad Request."""
    resp = client.post("/orders/ORD-1001/cancel")
    assert resp.status_code == 400
    assert "cannot be cancelled" in resp.json()["detail"]


def test_assistant_chat_endpoint(client):
    """Test /assistant/chat endpoint."""
    payload = {
        "message": "Where is order ORD-1001?",
        "customer_id": "CUS-001",
        "conversation_history": [],
        "llm_provider": "demo",
    }
    resp = client.post("/assistant/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert data["used_order_api"] is True
    assert "ORD-1001" in data["answer"]
