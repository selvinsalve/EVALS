import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.database import Base
from app.database.seed import seed_data
from app.services.order_service import OrderService


@pytest.fixture(scope="module")
def test_db():
    """Create an in-memory SQLite database pre-seeded with test data."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()
    seed_data(db)
    yield db
    db.close()


def test_order_retrieval(test_db):
    """Test retrieving an existing order with items and carrier."""
    service = OrderService(test_db)
    order = service.get_order("ORD-1001")
    assert order is not None
    assert order.order_id == "ORD-1001"
    assert order.status == "SHIPPED"
    assert order.carrier == "FedEx"
    assert len(order.items) == 2
    assert order.items[0].product_name == "Wireless Noise-Cancelling Headphones"


def test_order_not_found(test_db):
    """Test lookup for a non-existent order ID."""
    service = OrderService(test_db)
    order = service.get_order("ORD-9999")
    assert order is None


def test_customer_orders(test_db):
    """Test retrieving all orders for a specific customer."""
    service = OrderService(test_db)
    orders = service.get_customer_orders("CUS-001")
    assert len(orders) >= 3
    order_ids = [o.order_id for o in orders]
    assert "ORD-1001" in order_ids
    assert "ORD-1002" in order_ids


def test_latest_order_for_customer(test_db):
    """Test retrieving the latest order for a customer."""
    service = OrderService(test_db)
    latest = service.get_latest_order_for_customer("CUS-001")
    assert latest is not None
    assert latest.order_id in ("ORD-1003", "ORD-1001")


def test_successful_cancellation(test_db):
    """Test cancelling an order that has cancellation_allowed=True."""
    service = OrderService(test_db)
    # ORD-1003 is PROCESSING and cancellation_allowed is True
    order = service.get_order("ORD-1003")
    assert order.cancellation_allowed is True
    assert order.status == "PROCESSING"

    success, msg, cancel_resp = service.cancel_order("ORD-1003")
    assert success is True
    assert cancel_resp.status == "CANCELLED"

    # Verify updated in DB
    refreshed = service.get_order("ORD-1003")
    assert refreshed.status == "CANCELLED"
    assert refreshed.cancellation_allowed is False
    assert refreshed.payment_status == "REFUNDED"


def test_invalid_cancellation_shipped(test_db):
    """Test that cancelling a shipped order is rejected."""
    service = OrderService(test_db)
    # ORD-1001 is SHIPPED
    success, msg, cancel_resp = service.cancel_order("ORD-1001")
    assert success is False
    assert "cannot be cancelled because it has already been shipped" in msg

    # Status must remain SHIPPED
    order = service.get_order("ORD-1001")
    assert order.status == "SHIPPED"
