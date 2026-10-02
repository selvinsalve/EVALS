# Order Cancellation Policy

## Cancellation Windows and Rules
We strive to pack and dispatch orders as rapidly as possible. Because of our automated fulfillment pipeline, order cancellation is time-sensitive:

- **Orders in PLACED or CONFIRMED Status**:
  Cancellation is fully permitted and can be processed immediately through our AI Order Assistant, customer dashboard, or API. A 100% immediate refund is credited back to your original payment method.

- **Orders in PROCESSING Status**:
  Cancellation may be permitted if the warehouse pick-pack phase has not completed. The system will check the `cancellation_allowed` attribute. If eligible, the cancellation will execute immediately.

- **Orders in SHIPPED or OUT_FOR_DELIVERY Status**:
  Cancellation is strictly impossible once the package has been handed over to the carrier (FedEx, UPS, USPS, DHL). In this scenario:
  1. Allow the package to be delivered.
  2. Refuse delivery at the door or accept the parcel and initiate a standard return within our 30-day return window.

## How to Cancel an Order
1. Provide your Order ID (e.g. `Cancel ORD-1003`) to the AI Order Assistant.
2. The assistant will verify cancellation eligibility against live fulfillment databases.
3. If allowed, the order will be cancelled instantly, and a confirmation message with refund notice will be returned.
4. If not allowed, the assistant will inform you why the order cannot be cancelled and guide you through the return process upon delivery.

## Refused Deliveries & Undeliverable Packages
- Packages refused at the door will be returned to our fulfillment warehouse.
- A refund will be issued minus return shipping transit costs once received and inspected.
