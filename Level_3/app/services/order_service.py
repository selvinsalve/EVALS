from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from app.database.models import Order, Customer, OrderItem, Shipment
from app.schemas.order import (
    OrderResponse,
    OrderStatusResponse,
    OrderTrackingResponse,
    OrderCancelResponse,
)
from app.utils.logging import logger


class OrderService:
    """Service layer managing order queries, tracking, and cancellations."""

    def __init__(self, db: Session):
        self.db = db

    def get_order(self, order_id: str) -> Optional[Order]:
        """Fetch order by ID with related items and shipment eager-loaded."""
        clean_id = order_id.strip().upper()
        return (
            self.db.query(Order)
            .options(joinedload(Order.items), joinedload(Order.shipment))
            .filter(Order.order_id == clean_id)
            .first()
        )

    def get_customer_orders(self, customer_id: str) -> List[Order]:
        """Fetch all orders for a customer sorted by order_date descending."""
        clean_cid = customer_id.strip().upper()
        return (
            self.db.query(Order)
            .options(joinedload(Order.items), joinedload(Order.shipment))
            .filter(Order.customer_id == clean_cid)
            .order_by(Order.order_date.desc())
            .all()
        )

    def get_latest_order_for_customer(self, customer_id: str) -> Optional[Order]:
        """Fetch the single most recent order for a customer."""
        clean_cid = customer_id.strip().upper()
        return (
            self.db.query(Order)
            .options(joinedload(Order.items), joinedload(Order.shipment))
            .filter(Order.customer_id == clean_cid)
            .order_by(Order.order_date.desc())
            .first()
        )

    def get_order_status(self, order_id: str) -> Optional[OrderStatusResponse]:
        """Retrieve order status and delivery projection."""
        order = self.get_order(order_id)
        if not order:
            return None
        return OrderStatusResponse(
            order_id=order.order_id,
            status=order.status,
            estimated_delivery_date=order.estimated_delivery_date,
            tracking_number=order.tracking_number,
            carrier=order.carrier,
        )

    def get_order_tracking(self, order_id: str) -> Optional[OrderTrackingResponse]:
        """Retrieve live tracking details for an order."""
        order = self.get_order(order_id)
        if not order:
            return None

        if order.shipment:
            return OrderTrackingResponse(
                order_id=order.order_id,
                tracking_number=order.shipment.tracking_number,
                carrier=order.shipment.carrier,
                status=order.shipment.status,
                current_location=order.shipment.current_location,
                estimated_delivery=order.shipment.estimated_delivery,
            )

        # Fallback to order-level tracking attributes if shipment record is not created yet
        return OrderTrackingResponse(
            order_id=order.order_id,
            tracking_number=order.tracking_number,
            carrier=order.carrier,
            status=order.status,
            current_location="Awaiting carrier pickup" if order.status in ("PROCESSING", "CONFIRMED") else None,
            estimated_delivery=order.estimated_delivery_date,
        )

    def cancel_order(self, order_id: str) -> Tuple[bool, str, Optional[OrderCancelResponse]]:
        """
        Attempt to cancel an order according to business rules.
        Returns: (success: bool, reason_message: str, response: Optional[OrderCancelResponse])
        """
        clean_id = order_id.strip().upper()
        order = self.get_order(clean_id)

        if not order:
            return False, f"Order {clean_id} not found in our records.", None

        if order.status == "CANCELLED":
            return False, f"Order {clean_id} is already cancelled.", OrderCancelResponse(
                order_id=order.order_id,
                status=order.status,
                message="Order is already cancelled.",
                cancellation_allowed=False,
            )

        if order.status in ("SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED"):
            return False, (
                f"Order {clean_id} cannot be cancelled because it has already been {order.status.lower().replace('_', ' ')}. "
                "Once an order is in transit or delivered, you may initiate a return after receipt per our return policy."
            ), OrderCancelResponse(
                order_id=order.order_id,
                status=order.status,
                message=f"Order cannot be cancelled because its status is {order.status}.",
                cancellation_allowed=False,
            )

        if not order.cancellation_allowed:
            return False, (
                f"Order {clean_id} is currently non-cancellable because it has entered dispatch processing."
            ), OrderCancelResponse(
                order_id=order.order_id,
                status=order.status,
                message="Order is non-cancellable in its current processing stage.",
                cancellation_allowed=False,
            )

        # Permitted cancellation
        try:
            order.status = "CANCELLED"
            order.cancellation_allowed = False
            order.payment_status = "REFUNDED"
            cancelled_at = datetime.now(timezone.utc)

            # If a pending shipment existed, cancel shipment
            if order.shipment:
                order.shipment.status = "CANCELLED"

            self.db.commit()
            self.db.refresh(order)

            logger.info("Order %s successfully cancelled.", clean_id)
            return True, f"Order {clean_id} has been successfully cancelled and your refund has been processed.", OrderCancelResponse(
                order_id=order.order_id,
                status="CANCELLED",
                message=f"Order {clean_id} successfully cancelled. A full refund has been credited.",
                cancellation_allowed=False,
                cancelled_at=cancelled_at,
            )
        except Exception as e:
            self.db.rollback()
            logger.error("Failed to cancel order %s: %s", clean_id, e)
            return False, f"An internal error occurred while trying to cancel order {clean_id}.", None
