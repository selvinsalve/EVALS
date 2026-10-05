from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.services.order_service import OrderService
from app.schemas.order import (
    OrderResponse,
    OrderStatusResponse,
    OrderTrackingResponse,
    OrderItemSchema,
    OrderCancelResponse,
)

router = APIRouter(prefix="", tags=["Orders"])


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, db: Session = Depends(get_db)) -> OrderResponse:
    """Retrieve full details of an order by ID."""
    service = OrderService(db)
    order = service.get_order(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id.upper()} not found.",
        )
    return OrderResponse.model_validate(order)


@router.get("/customers/{customer_id}/orders", response_model=List[OrderResponse])
def get_customer_orders(customer_id: str, db: Session = Depends(get_db)) -> List[OrderResponse]:
    """Retrieve all orders placed by a specific customer."""
    service = OrderService(db)
    orders = service.get_customer_orders(customer_id)
    return [OrderResponse.model_validate(o) for o in orders]


@router.get("/orders/{order_id}/status", response_model=OrderStatusResponse)
def get_order_status(order_id: str, db: Session = Depends(get_db)) -> OrderStatusResponse:
    """Retrieve status and estimated delivery date for an order."""
    service = OrderService(db)
    status_resp = service.get_order_status(order_id)
    if not status_resp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id.upper()} not found.",
        )
    return status_resp


@router.get("/orders/{order_id}/tracking", response_model=OrderTrackingResponse)
def get_order_tracking(order_id: str, db: Session = Depends(get_db)) -> OrderTrackingResponse:
    """Retrieve carrier tracking information and current transit location."""
    service = OrderService(db)
    tracking = service.get_order_tracking(order_id)
    if not tracking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id.upper()} not found.",
        )
    return tracking


@router.get("/orders/{order_id}/items", response_model=List[OrderItemSchema])
def get_order_items(order_id: str, db: Session = Depends(get_db)) -> List[OrderItemSchema]:
    """Retrieve item line items for an order."""
    service = OrderService(db)
    order = service.get_order(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id.upper()} not found.",
        )
    return [OrderItemSchema.model_validate(item) for item in order.items]


@router.post("/orders/{order_id}/cancel", response_model=OrderCancelResponse)
def cancel_order(order_id: str, db: Session = Depends(get_db)) -> OrderCancelResponse:
    """
    Cancel an order if eligible according to order state.
    Returns 400 Bad Request if the order cannot be cancelled (e.g., already shipped).
    """
    service = OrderService(db)
    success, reason, cancel_response = service.cancel_order(order_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=reason,
        )
    return cancel_response
