from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database.database import engine, Base, SessionLocal
from app.database.models import Customer, Order, OrderItem, Shipment
from app.utils.logging import logger


def init_db() -> None:
    """Initialize database tables."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")


def seed_data(db: Session = None) -> None:
    """Seed the database with realistic sample e-commerce data."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Check if already seeded
        if db.query(Customer).first():
            logger.info("Database already contains data. Skipping seed.")
            return

        logger.info("Seeding realistic e-commerce data...")

        # 1. Create Customers (10 customers)
        customers_data = [
            {"customer_id": "CUS-001", "name": "Sarah Connor", "email": "sarah.connor@example.com", "phone": "+1-555-0101"},
            {"customer_id": "CUS-002", "name": "Alex Mercer", "email": "alex.mercer@example.com", "phone": "+1-555-0102"},
            {"customer_id": "CUS-003", "name": "Elena Fisher", "email": "elena.fisher@example.com", "phone": "+1-555-0103"},
            {"customer_id": "CUS-004", "name": "Marcus Vance", "email": "marcus.vance@example.com", "phone": "+1-555-0104"},
            {"customer_id": "CUS-005", "name": "Diana Prince", "email": "diana.prince@example.com", "phone": "+1-555-0105"},
            {"customer_id": "CUS-006", "name": "James Holden", "email": "james.holden@example.com", "phone": "+1-555-0106"},
            {"customer_id": "CUS-007", "name": "Naomi Nagata", "email": "naomi.nagata@example.com", "phone": "+1-555-0107"},
            {"customer_id": "CUS-008", "name": "Arthur Dent", "email": "arthur.dent@example.com", "phone": "+1-555-0108"},
            {"customer_id": "CUS-009", "name": "Tess Coleman", "email": "tess.coleman@example.com", "phone": "+1-555-0109"},
            {"customer_id": "CUS-010", "name": "Victor Stone", "email": "victor.stone@example.com", "phone": "+1-555-0110"},
        ]

        now = datetime(2026, 10, 1, 12, 0, 0)

        for c_data in customers_data:
            customer = Customer(
                customer_id=c_data["customer_id"],
                name=c_data["name"],
                email=c_data["email"],
                phone=c_data["phone"],
                created_at=now - timedelta(days=90),
            )
            db.add(customer)
        db.flush()

        # 2. Create Orders, Items, Shipments
        orders_spec = [
            # CUS-001 Orders
            {
                "order_id": "ORD-1001",
                "customer_id": "CUS-001",
                "order_date": now - timedelta(days=2),
                "status": "SHIPPED",
                "total_amount": 129.99,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=3),
                "shipping_address": "742 Evergreen Terrace, Springfield, OR 97477",
                "tracking_number": "FDX-99482110",
                "carrier": "FedEx",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-HEADPHONES-01", "product_name": "Wireless Noise-Cancelling Headphones", "quantity": 1, "unit_price": 99.99},
                    {"product_id": "PROD-CABLE-02", "product_name": "Braided USB-C Fast Charging Cable (2m)", "quantity": 2, "unit_price": 15.00},
                ],
                "shipment": {
                    "tracking_number": "FDX-99482110",
                    "carrier": "FedEx",
                    "status": "IN_TRANSIT",
                    "shipped_at": now - timedelta(days=1),
                    "estimated_delivery": now + timedelta(days=3),
                    "current_location": "Memphis Logistics Superhub, TN",
                },
            },
            {
                "order_id": "ORD-1002",
                "customer_id": "CUS-001",
                "order_date": now - timedelta(days=20),
                "status": "DELIVERED",
                "total_amount": 54.50,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=16),
                "actual_delivery_date": now - timedelta(days=16),
                "shipping_address": "742 Evergreen Terrace, Springfield, OR 97477",
                "tracking_number": "UPS-77182901",
                "carrier": "UPS",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-STAND-01", "product_name": "Adjustable Aluminum Laptop Stand", "quantity": 1, "unit_price": 45.00},
                    {"product_id": "PROD-MOUSEPAD-01", "product_name": "Water-Resistant Desk Mat", "quantity": 1, "unit_price": 9.50},
                ],
                "shipment": {
                    "tracking_number": "UPS-77182901",
                    "carrier": "UPS",
                    "status": "DELIVERED",
                    "shipped_at": now - timedelta(days=19),
                    "estimated_delivery": now - timedelta(days=16),
                    "delivered_at": now - timedelta(days=16),
                    "current_location": "Delivered to Front Porch, Springfield, OR",
                },
            },
            {
                "order_id": "ORD-1003",
                "customer_id": "CUS-001",
                "order_date": now - timedelta(hours=4),
                "status": "PROCESSING",
                "total_amount": 89.00,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=5),
                "shipping_address": "742 Evergreen Terrace, Springfield, OR 97477",
                "tracking_number": None,
                "carrier": None,
                "payment_status": "PAID",
                "cancellation_allowed": True,  # Cancellable!
                "items": [
                    {"product_id": "PROD-KEYBOARD-03", "product_name": "Mechanical Gaming Keyboard RGB", "quantity": 1, "unit_price": 89.00},
                ],
            },
            {
                "order_id": "ORD-1004",
                "customer_id": "CUS-001",
                "order_date": now - timedelta(days=40),
                "status": "CANCELLED",
                "total_amount": 34.00,
                "currency": "USD",
                "estimated_delivery_date": None,
                "shipping_address": "742 Evergreen Terrace, Springfield, OR 97477",
                "tracking_number": None,
                "carrier": None,
                "payment_status": "REFUNDED",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-MUG-01", "product_name": "Ceramic Thermal Travel Mug 16oz", "quantity": 1, "unit_price": 34.00},
                ],
            },
            # CUS-002 Orders
            {
                "order_id": "ORD-1005",
                "customer_id": "CUS-002",
                "order_date": now - timedelta(days=7),
                "status": "DELAYED",
                "total_amount": 249.99,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=2),  # Expected 2 days ago!
                "shipping_address": "1204 Pine Street, Seattle, WA 98101",
                "tracking_number": "UPS-8839102",
                "carrier": "UPS",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-MONITOR-27", "product_name": "27-inch 4K UHD IPS Monitor", "quantity": 1, "unit_price": 249.99},
                ],
                "shipment": {
                    "tracking_number": "UPS-8839102",
                    "carrier": "UPS",
                    "status": "DELAYED",
                    "shipped_at": now - timedelta(days=6),
                    "estimated_delivery": now - timedelta(days=2),
                    "current_location": "Chicago Sorting Facility - Severe weather transit delay",
                },
            },
            {
                "order_id": "ORD-1006",
                "customer_id": "CUS-002",
                "order_date": now - timedelta(days=3),
                "status": "OUT_FOR_DELIVERY",
                "total_amount": 42.00,
                "currency": "USD",
                "estimated_delivery_date": now,
                "shipping_address": "1204 Pine Street, Seattle, WA 98101",
                "tracking_number": "USPS-94001092",
                "carrier": "USPS",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-SMARTPLUG-02", "product_name": "Wi-Fi Smart Plug 4-Pack", "quantity": 1, "unit_price": 42.00},
                ],
                "shipment": {
                    "tracking_number": "USPS-94001092",
                    "carrier": "USPS",
                    "status": "OUT_FOR_DELIVERY",
                    "shipped_at": now - timedelta(days=2),
                    "estimated_delivery": now,
                    "current_location": "Seattle Central Postal Depot - On delivery vehicle",
                },
            },
            {
                "order_id": "ORD-1007",
                "customer_id": "CUS-002",
                "order_date": now - timedelta(hours=1),
                "status": "PLACED",
                "total_amount": 115.00,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=4),
                "shipping_address": "1204 Pine Street, Seattle, WA 98101",
                "tracking_number": None,
                "carrier": None,
                "payment_status": "PAID",
                "cancellation_allowed": True,
                "items": [
                    {"product_id": "PROD-POWERBANK-20", "product_name": "20000mAh Portable Power Bank", "quantity": 1, "unit_price": 55.00},
                    {"product_id": "PROD-WEBCAM-HD", "product_name": "1080P Streaming Webcam with Privacy Cover", "quantity": 1, "unit_price": 60.00},
                ],
            },
            # CUS-003 Orders
            {
                "order_id": "ORD-1008",
                "customer_id": "CUS-003",
                "order_date": now - timedelta(days=12),
                "status": "RETURN_REQUESTED",
                "total_amount": 180.00,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=8),
                "actual_delivery_date": now - timedelta(days=8),
                "shipping_address": "505 Elmwood Avenue, Buffalo, NY 14222",
                "tracking_number": "FDX-88290123",
                "carrier": "FedEx",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-CHAIR-ERG", "product_name": "Ergonomic Lumbar Office Cushion", "quantity": 2, "unit_price": 90.00},
                ],
            },
            {
                "order_id": "ORD-1009",
                "customer_id": "CUS-003",
                "order_date": now - timedelta(days=25),
                "status": "REFUNDED",
                "total_amount": 75.00,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=20),
                "shipping_address": "505 Elmwood Avenue, Buffalo, NY 14222",
                "tracking_number": "UPS-11029481",
                "carrier": "UPS",
                "payment_status": "REFUNDED",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-MOUSE-VERT", "product_name": "Ergonomic Vertical Wireless Mouse", "quantity": 1, "unit_price": 75.00},
                ],
            },
            # CUS-004 Orders
            {
                "order_id": "ORD-1010",
                "customer_id": "CUS-004",
                "order_date": now - timedelta(days=1),
                "status": "CONFIRMED",
                "total_amount": 310.00,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=4),
                "shipping_address": "330 Biscayne Blvd, Miami, FL 33132",
                "tracking_number": None,
                "carrier": None,
                "payment_status": "PAID",
                "cancellation_allowed": True,
                "items": [
                    {"product_id": "PROD-SMARTWATCH-04", "product_name": "Titanium Smartwatch Series 6", "quantity": 1, "unit_price": 310.00},
                ],
            },
            {
                "order_id": "ORD-1011",
                "customer_id": "CUS-004",
                "order_date": now - timedelta(days=15),
                "status": "DELIVERED",
                "total_amount": 62.50,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=11),
                "actual_delivery_date": now - timedelta(days=11),
                "shipping_address": "330 Biscayne Blvd, Miami, FL 33132",
                "tracking_number": "FDX-77381920",
                "carrier": "FedEx",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-SPEAKER-MINI", "product_name": "Bluetooth Waterproof Speaker", "quantity": 1, "unit_price": 62.50},
                ],
            },
            # CUS-005 Orders
            {
                "order_id": "ORD-1012",
                "customer_id": "CUS-005",
                "order_date": now - timedelta(days=4),
                "status": "SHIPPED",
                "total_amount": 199.95,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=1),
                "shipping_address": "88 Commonwealth Ave, Boston, MA 02215",
                "tracking_number": "FDX-44910291",
                "carrier": "FedEx",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-COFFEEMAKER-01", "product_name": "Programmable Espresso Machine", "quantity": 1, "unit_price": 199.95},
                ],
                "shipment": {
                    "tracking_number": "FDX-44910291",
                    "carrier": "FedEx",
                    "status": "IN_TRANSIT",
                    "shipped_at": now - timedelta(days=3),
                    "estimated_delivery": now + timedelta(days=1),
                    "current_location": "Newark Regional Hub, NJ",
                },
            },
            {
                "order_id": "ORD-1013",
                "customer_id": "CUS-005",
                "order_date": now - timedelta(hours=8),
                "status": "PROCESSING",
                "total_amount": 45.00,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=5),
                "shipping_address": "88 Commonwealth Ave, Boston, MA 02215",
                "tracking_number": None,
                "carrier": None,
                "payment_status": "PAID",
                "cancellation_allowed": True,
                "items": [
                    {"product_id": "PROD-COFFEEBEANS-1KG", "product_name": "Organic Fair-Trade Coffee Beans 1kg", "quantity": 2, "unit_price": 22.50},
                ],
            },
            # CUS-006 Orders
            {
                "order_id": "ORD-1014",
                "customer_id": "CUS-006",
                "order_date": now - timedelta(days=5),
                "status": "DELAYED",
                "total_amount": 140.00,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=1),
                "shipping_address": "410 North Michigan Ave, Chicago, IL 60611",
                "tracking_number": "UPS-99018273",
                "carrier": "UPS",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-BACKPACK-TRAVEL", "product_name": "Anti-Theft Commuter Backpack 30L", "quantity": 1, "unit_price": 140.00},
                ],
                "shipment": {
                    "tracking_number": "UPS-99018273",
                    "carrier": "UPS",
                    "status": "DELAYED",
                    "shipped_at": now - timedelta(days=4),
                    "estimated_delivery": now - timedelta(days=1),
                    "current_location": "Des Moines Transit Depot - Train mechanical hold",
                },
            },
            {
                "order_id": "ORD-1015",
                "customer_id": "CUS-006",
                "order_date": now - timedelta(days=35),
                "status": "DELIVERED",
                "total_amount": 25.00,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=30),
                "actual_delivery_date": now - timedelta(days=30),
                "shipping_address": "410 North Michigan Ave, Chicago, IL 60611",
                "tracking_number": "USPS-99201928",
                "carrier": "USPS",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-PASSPORT-WALLET", "product_name": "RFID Blocking Leather Passport Holder", "quantity": 1, "unit_price": 25.00},
                ],
            },
            # CUS-007 Orders
            {
                "order_id": "ORD-1016",
                "customer_id": "CUS-007",
                "order_date": now - timedelta(hours=3),
                "status": "PLACED",
                "total_amount": 520.00,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=3),
                "shipping_address": "100 Innovation Way, Austin, TX 78701",
                "tracking_number": None,
                "carrier": None,
                "payment_status": "PAID",
                "cancellation_allowed": True,
                "items": [
                    {"product_id": "PROD-TABLET-11", "product_name": "Pro 11-inch OLED Tablet 256GB", "quantity": 1, "unit_price": 480.00},
                    {"product_id": "PROD-PEN-STYLUS", "product_name": "Active Precision Stylus Pen", "quantity": 1, "unit_price": 40.00},
                ],
            },
            {
                "order_id": "ORD-1017",
                "customer_id": "CUS-007",
                "order_date": now - timedelta(days=10),
                "status": "DELIVERED",
                "total_amount": 80.00,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=6),
                "actual_delivery_date": now - timedelta(days=6),
                "shipping_address": "100 Innovation Way, Austin, TX 78701",
                "tracking_number": "FDX-55102938",
                "carrier": "FedEx",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-DOCK-10IN1", "product_name": "10-in-1 USB-C Triple Display Hub", "quantity": 1, "unit_price": 80.00},
                ],
            },
            # CUS-008 Orders
            {
                "order_id": "ORD-1018",
                "customer_id": "CUS-008",
                "order_date": now - timedelta(days=3),
                "status": "SHIPPED",
                "total_amount": 78.50,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=2),
                "shipping_address": "42 Galaxy Road, London, OH 43140",
                "tracking_number": "DHL-102938475",
                "carrier": "DHL Express",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-TOWEL-MICRO", "product_name": "Space-Age Microfiber Towel Set", "quantity": 2, "unit_price": 24.25},
                    {"product_id": "PROD-TORCH-LED", "product_name": "High-Lumen Rechargeable LED Flashlight", "quantity": 1, "unit_price": 30.00},
                ],
                "shipment": {
                    "tracking_number": "DHL-102938475",
                    "carrier": "DHL Express",
                    "status": "IN_TRANSIT",
                    "shipped_at": now - timedelta(days=2),
                    "estimated_delivery": now + timedelta(days=2),
                    "current_location": "Cincinnati Sorting Hub, OH",
                },
            },
            {
                "order_id": "ORD-1019",
                "customer_id": "CUS-008",
                "order_date": now - timedelta(days=18),
                "status": "DELIVERED",
                "total_amount": 110.00,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=14),
                "actual_delivery_date": now - timedelta(days=14),
                "shipping_address": "42 Galaxy Road, London, OH 43140",
                "tracking_number": "FDX-99882211",
                "carrier": "FedEx",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-HEADPHONES-ANC", "product_name": "Over-Ear Wireless Studio Headphones", "quantity": 1, "unit_price": 110.00},
                ],
            },
            # CUS-009 Orders
            {
                "order_id": "ORD-1020",
                "customer_id": "CUS-009",
                "order_date": now - timedelta(days=1),
                "status": "PROCESSING",
                "total_amount": 64.00,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=4),
                "shipping_address": "15 Maple Grove Way, Denver, CO 80203",
                "tracking_number": None,
                "carrier": None,
                "payment_status": "PAID",
                "cancellation_allowed": True,
                "items": [
                    {"product_id": "PROD-YOGAMAT-PRO", "product_name": "Eco-Friendly Non-Slip Yoga Mat 6mm", "quantity": 1, "unit_price": 48.00},
                    {"product_id": "PROD-STRAP-01", "product_name": "Stretching Resistance Strap", "quantity": 1, "unit_price": 16.00},
                ],
            },
            {
                "order_id": "ORD-1021",
                "customer_id": "CUS-009",
                "order_date": now - timedelta(days=60),
                "status": "DELIVERED",
                "total_amount": 135.00,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=55),
                "actual_delivery_date": now - timedelta(days=55),
                "shipping_address": "15 Maple Grove Way, Denver, CO 80203",
                "tracking_number": "UPS-55019283",
                "carrier": "UPS",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-DUMBBELL-SET", "product_name": "Adjustable Dumbbell Pair 20kg", "quantity": 1, "unit_price": 135.00},
                ],
            },
            # CUS-010 Orders
            {
                "order_id": "ORD-1022",
                "customer_id": "CUS-010",
                "order_date": now - timedelta(days=2),
                "status": "SHIPPED",
                "total_amount": 349.00,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=2),
                "shipping_address": "200 Cybernetic Plaza, Detroit, MI 48226",
                "tracking_number": "FDX-11223344",
                "carrier": "FedEx",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-DRONE-4K", "product_name": "Compact Foldable 4K GPS Drone", "quantity": 1, "unit_price": 349.00},
                ],
                "shipment": {
                    "tracking_number": "FDX-11223344",
                    "carrier": "FedEx",
                    "status": "IN_TRANSIT",
                    "shipped_at": now - timedelta(days=1),
                    "estimated_delivery": now + timedelta(days=2),
                    "current_location": "Indianapolis Hub, IN",
                },
            },
            {
                "order_id": "ORD-1023",
                "customer_id": "CUS-010",
                "order_date": now - timedelta(hours=2),
                "status": "PLACED",
                "total_amount": 29.99,
                "currency": "USD",
                "estimated_delivery_date": now + timedelta(days=5),
                "shipping_address": "200 Cybernetic Plaza, Detroit, MI 48226",
                "tracking_number": None,
                "carrier": None,
                "payment_status": "PAID",
                "cancellation_allowed": True,
                "items": [
                    {"product_id": "PROD-DRONEBAT-02", "product_name": "Spare Intelligent Flight Battery", "quantity": 1, "unit_price": 29.99},
                ],
            },
            {
                "order_id": "ORD-1024",
                "customer_id": "CUS-010",
                "order_date": now - timedelta(days=8),
                "status": "CANCELLED",
                "total_amount": 19.99,
                "currency": "USD",
                "estimated_delivery_date": None,
                "shipping_address": "200 Cybernetic Plaza, Detroit, MI 48226",
                "tracking_number": None,
                "carrier": None,
                "payment_status": "REFUNDED",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-PROPELLER-04", "product_name": "Quick-Release Propeller Pack (4 Pairs)", "quantity": 1, "unit_price": 19.99},
                ],
            },
            {
                "order_id": "ORD-1025",
                "customer_id": "CUS-001",
                "order_date": now - timedelta(days=15),
                "status": "DELIVERED",
                "total_amount": 15.99,
                "currency": "USD",
                "estimated_delivery_date": now - timedelta(days=12),
                "actual_delivery_date": now - timedelta(days=12),
                "shipping_address": "742 Evergreen Terrace, Springfield, OR 97477",
                "tracking_number": "USPS-99881122",
                "carrier": "USPS",
                "payment_status": "PAID",
                "cancellation_allowed": False,
                "items": [
                    {"product_id": "PROD-CLEANER-01", "product_name": "Screen Cleaning Kit with Microfiber Cloths", "quantity": 1, "unit_price": 15.99},
                ],
            },
        ]

        for spec in orders_spec:
            order = Order(
                order_id=spec["order_id"],
                customer_id=spec["customer_id"],
                order_date=spec["order_date"],
                status=spec["status"],
                total_amount=spec["total_amount"],
                currency=spec["currency"],
                estimated_delivery_date=spec["estimated_delivery_date"],
                actual_delivery_date=spec.get("actual_delivery_date"),
                shipping_address=spec["shipping_address"],
                tracking_number=spec.get("tracking_number"),
                carrier=spec.get("carrier"),
                payment_status=spec["payment_status"],
                cancellation_allowed=spec["cancellation_allowed"],
            )
            db.add(order)
            db.flush()

            for item_spec in spec.get("items", []):
                item = OrderItem(
                    order_id=order.order_id,
                    product_id=item_spec["product_id"],
                    product_name=item_spec["product_name"],
                    quantity=item_spec["quantity"],
                    unit_price=item_spec["unit_price"],
                )
                db.add(item)

            if "shipment" in spec:
                s_spec = spec["shipment"]
                shipment = Shipment(
                    order_id=order.order_id,
                    tracking_number=s_spec["tracking_number"],
                    carrier=s_spec["carrier"],
                    status=s_spec["status"],
                    shipped_at=s_spec.get("shipped_at"),
                    estimated_delivery=s_spec.get("estimated_delivery"),
                    delivered_at=s_spec.get("delivered_at"),
                    current_location=s_spec.get("current_location"),
                )
                db.add(shipment)

        db.commit()
        logger.info("Database successfully seeded with 10 customers and 25 orders.")

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        if close_db:
            db.close()
