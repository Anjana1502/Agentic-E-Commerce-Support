"""In-memory mock data: customers, orders, tracking events and the product catalog.

Everything is hard-coded so the agent demo runs offline, reproducibly and without
any external backend. In a production deployment this module is replaced by the
real ERP / order-management database and the merchant product feed.
"""

from datetime import date

TODAY = date(2026, 9, 9)


ORDERS = {
    "ORD-1024": {
        "order_id": "ORD-1024",
        "customer_id": "CUST-1001",
        "created": "2026-08-20",
        "status": "Shipped",
        "payment": "UPI",
        "carrier": "BlueDart",
        "delivered": None,
        "tracking": [
            ("2026-08-21", "Order accepted"),
            ("2026-08-22", "Shipment picked up from our fulfilment centre"),
            ("2026-08-24", "In transit - Hub, Chennai"),
            ("2026-09-08", "Out for delivery"),
        ],
        "items": [
            {"sku": "SKU-101", "name": "Dolby Wireless Headphones", "qty": 1, "price": 2499.0},
            {"sku": "SKU-202", "name": "Pro Yoga Mat", "qty": 1, "price": 899.0},
        ],
    },
    "ORD-1025": {
        "order_id": "ORD-1025",
        "customer_id": "CUST-1001",
        "created": "2026-09-05",
        "status": "Processing",
        "payment": "Credit Card",
        "carrier": "",
        "delivered": None,
        "tracking": [],
        "items": [
            {"sku": "SKU-303", "name": "Pulse Smart Watch", "qty": 1, "price": 3999.0},
        ],
    },
    "ORD-1026": {
        "order_id": "ORD-1026",
        "customer_id": "CUST-1001",
        "created": "2026-08-28",
        "status": "Delivered",
        "payment": "UPI",
        "carrier": "BlueDart",
        "delivered": "2026-09-04",
        "tracking": [
            ("2026-08-29", "Shipment picked up from our fulfilment centre"),
            ("2026-09-03", "In transit - Hub, Mumbai"),
            ("2026-09-04", "Delivered"),
        ],
        "items": [
            {"sku": "SKU-404", "name": "Trail Urban Backpack", "qty": 1, "price": 1799.0},
        ],
    },
    "ORD-1027": {
        "order_id": "ORD-1027",
        "customer_id": "CUST-1001",
        "created": "2026-07-10",
        "status": "Delivered",
        "payment": "Net Banking",
        "carrier": "Delhivery",
        "delivered": "2026-07-18",
        "tracking": [
            ("2026-07-11", "Shipment picked up from our fulfilment centre"),
            ("2026-07-18", "Delivered"),
        ],
        "items": [
            {"sku": "SKU-501", "name": "Polarized Sunglasses", "qty": 2, "price": 999.0},
        ],
    },
    "ORD-1028": {
        "order_id": "ORD-1028",
        "customer_id": "CUST-1001",
        "created": "2026-08-10",
        "status": "Cancelled",
        "payment": "UPI",
        "carrier": "",
        "delivered": None,
        "tracking": [],
        "items": [
            {"sku": "SKU-808", "name": "LED Desk Lamp", "qty": 1, "price": 649.0},
        ],
    },
    "ORD-9001": {
        "order_id": "ORD-9001",
        "customer_id": "CUST-2002",
        "created": "2026-08-01",
        "status": "Delivered",
        "payment": "UPI",
        "carrier": "Delhivery",
        "delivered": "2026-08-06",
        "tracking": [("2026-08-06", "Delivered")],
        "items": [
            {"sku": "SKU-606", "name": "RoboVac 500 Home Vacuum", "qty": 1, "price": 8499.0},
        ],
    },
}


PRODUCTS = {
    "SKU-101": {
        "name": "Dolby Wireless Headphones", "category": "Electronics", "price": 2499.0,
        "stock": 34, "rating": 4.6,
        "description": "Over-ear wireless headphones with active noise cancellation, 30h battery and USB-C fast charge.",
    },
    "SKU-102": {
        "name": "Echo True Wireless Earbuds", "category": "Electronics", "price": 1299.0,
        "stock": 120, "rating": 4.3,
        "description": "Lightweight TWS earbuds with touch controls and a 24h total playtime case.",
    },
    "SKU-303": {
        "name": "Pulse Smart Watch", "category": "Electronics", "price": 3999.0,
        "stock": 8, "rating": 4.5,
        "description": "Fitness smart watch with AMOLED display, heart-rate and sleep tracking.",
    },
    "SKU-404": {
        "name": "Trail Urban Backpack", "category": "Fashion", "price": 1799.0,
        "stock": 55, "rating": 4.4,
        "description": "Water-resistant 25L laptop backpack with padded straps and USB port.",
    },
    "SKU-202": {
        "name": "Pro Yoga Mat", "category": "Fitness", "price": 899.0,
        "stock": 41, "rating": 4.7,
        "description": "6mm TPE yoga mat with alignment lines and carry strap.",
    },
    "SKU-501": {
        "name": "Polarized Sunglasses", "category": "Fashion", "price": 999.0,
        "stock": 63, "rating": 4.2,
        "description": "UV400 polarized sunglasses with a sturdy travel case.",
    },
    "SKU-606": {
        "name": "RoboVac 500 Home Vacuum", "category": "Home & Living", "price": 8499.0,
        "stock": 5, "rating": 4.5,
        "description": "Robot vacuum with LiDAR navigation, mopping mode and app control.",
    },
    "SKU-707": {
        "name": "Travel Organizer Set", "category": "Fashion", "price": 499.0,
        "stock": 210, "rating": 4.8,
        "description": "6-piece compression packing cube set for neat travel bags.",
    },
    "SKU-808": {
        "name": "LED Desk Lamp", "category": "Home & Living", "price": 649.0,
        "stock": 88, "rating": 4.1,
        "description": "Dimmable LED study lamp with 3 colour modes and USB charging port.",
    },
    "SKU-909": {
        "name": "Hydrolock Water Bottle 1L", "category": "Fitness", "price": 299.0,
        "stock": 300, "rating": 4.6,
        "description": "Leak-proof stainless steel 1L bottle with time markings.",
    },
}


CUSTOMERS = {
    "CUST-1001": {"name": "Anjana"},
    "CUST-2002": {"name": "Rahul"},
}

DEMO_CUSTOMER_ID = "CUST-1001"
DEMO_CUSTOMER_NAME = CUSTOMERS[DEMO_CUSTOMER_ID]["name"]

SHIPPING_FEE = 49.0
FREE_SHIPPING_MIN = 499.0
RETURN_WINDOW_DAYS = 30
REFUND_PROCESSING_DAYS = "5-7 business days"
WARRANTY_DURATION = "1 year limited warranty"


def get_order(order_id):
    """Return the order for `order_id`, or None if it does not exist."""
    return ORDERS.get(order_id.upper() if isinstance(order_id, str) else order_id)


def order_total(order):
    """Return the order subtotal."""
    return round(sum(it["price"] * it["qty"] for it in order["items"]), 2)


def days_since(raw_date, today=TODAY):
    """Days elapsed between a raw ISO date string and `today`."""
    if not raw_date:
        return None
    if isinstance(raw_date, date):
        return (today - raw_date).days
    dt = date.fromisoformat(raw_date)
    return (today - dt).days