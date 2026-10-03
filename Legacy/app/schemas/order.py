from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class OrderItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    product_name: str
    quantity: int
    unit_price: float


class ShipmentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tracking_number: str
    carrier: str
    status: str
    shipped_at: Optional[datetime] = None
    estimated_delivery: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    current_location: Optional[str] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    customer_id: str
    order_date: datetime
    status: str
    total_amount: float
    currency: str
    estimated_delivery_date: Optional[datetime] = None
    actual_delivery_date: Optional[datetime] = None
    shipping_address: str
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    payment_status: str
    cancellation_allowed: bool
    items: List[OrderItemSchema] = []
    shipment: Optional[ShipmentSchema] = None


class OrderStatusResponse(BaseModel):
    order_id: str
    status: str
    estimated_delivery_date: Optional[datetime] = None
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None


class OrderTrackingResponse(BaseModel):
    order_id: str
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    status: Optional[str] = None
    current_location: Optional[str] = None
    estimated_delivery: Optional[datetime] = None


class OrderCancelResponse(BaseModel):
    order_id: str
    status: str
    message: str
    cancellation_allowed: bool
    cancelled_at: Optional[datetime] = None


class CustomerOrdersResponse(BaseModel):
    customer_id: str
    orders: List[OrderResponse]
