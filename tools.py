"""The agent's tool registry.

Each tool is a plain function wrapped in a :class:`Tool`. The agent does not
hard-code business logic; it *plans* a sequence of tool calls and executes them,
which is exactly the agentic pattern (an LLM would pick the same tools from the
registry descriptions - see README).

Tools raise :class:`ToolError` subclasses to flag failures the agent should talk
about naturally instead of crashing.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from . import data, kb


class ToolError(Exception):
    """Base class for tool failures."""


class OrderNotFoundError(ToolError):
    pass


class NotOwnedError(ToolError):
    pass


class NotAllowedError(ToolError):
    pass


@dataclass
class Tool:
    name: str
    description: str
    fn: callable


def _owned(order, session):
    return order["customer_id"] == session.customer_id


def get_order_status(session, order_id):
    """Return the live status of an order together with the latest event."""
    order = data.get_order(order_id)
    if order is None:
        raise OrderNotFoundError(order_id)
    if not _owned(order, session):
        raise NotOwnedError(order_id)
    if order["tracking"]:
        latest_date, latest_text = order["tracking"][-1]
    else:
        latest_date, latest_text = order["created"], "Order placed"
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "latest_event": latest_text,
        "event_date": latest_date,
        "eta": None,
    }


def get_order_details(session, order_id):
    """Return full order details: items, totals, payment, dates, status."""
    order = data.get_order(order_id)
    if order is None:
        raise OrderNotFoundError(order_id)
    if not _owned(order, session):
        raise NotOwnedError(order_id)
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "created": order["created"],
        "payment": order["payment"],
        "items": list(order["items"]),
        "total": data.order_total(order),
    }


def track_shipment(session, order_id):
    """Return the shipment tracking trail and delivery ETA, if shipped."""
    order = data.get_order(order_id)
    if order is None:
        raise OrderNotFoundError(order_id)
    if not _owned(order, session):
        raise NotOwnedError(order_id)
    if order["status"] == "Delivered":
        return {"order_id": order["order_id"], "delivered": True,
                "events": list(order["tracking"])}
    if order["status"] == "Shipped":
        eta = (datetime.fromisoformat(order["tracking"][-1][0]) + timedelta(days=2)).date().isoformat()
        return {"order_id": order["order_id"], "delivered": False,
                "carrier": order["carrier"], "eta": eta,
                "events": list(order["tracking"])}
    return {"order_id": order["order_id"], "delivered": False, "events": [],
            "note": "This order has not been handed to a courier yet."}


def check_return_eligibility(session, order_id):
    """Check whether an order can still be returned under the 30-day policy."""
    order = data.get_order(order_id)
    if order is None:
        raise OrderNotFoundError(order_id)
    if not _owned(order, session):
        raise NotOwnedError(order_id)
    if order["status"] != "Delivered":
        return {"order_id": order["order_id"], "eligible": False,
                "reason": "Returns are possible only after the order is delivered."}
    elapsed_days = data.days_since(order["delivered"])
    if elapsed_days is not None and elapsed_days > data.RETURN_WINDOW_DAYS:
        return {"order_id": order["order_id"], "eligible": False,
                "reason": "The 30-day return window on this order ended %d day(s) ago."
                          % elapsed_days,
                "elapsed_days": elapsed_days,
                "window_days": data.RETURN_WINDOW_DAYS}
    return {"order_id": order["order_id"], "eligible": True,
            "window_days": data.RETURN_WINDOW_DAYS,
            "elapsed_days": elapsed_days}


def refund_estimate(session, order_id, reason="changed my mind"):
    """Estimate the refund amount for a return (deducts pickup fee unless defective)."""
    order = data.get_order(order_id)
    if order is None:
        raise OrderNotFoundError(order_id)
    if not _owned(order, session):
        raise NotOwnedError(order_id)
    total = data.order_total(order)
    fee = 0.0 if reason == "defective" else data.SHIPPING_FEE
    return {"order_id": order["order_id"], "item_total": total, "pickup_fee": fee,
            "estimated_refund": round(total - fee, 2),
            "disbursed_in": data.REFUND_PROCESSING_DAYS}


def initiate_return(session, order_id, reason="changed my mind"):
    """Create the return request (RMA) for a delivered, in-window order."""
    eligibility = check_return_eligibility(session, order_id)
    if not eligibility["eligible"]:
        raise NotAllowedError("Return not allowed: " + eligibility["reason"])
    estimate = refund_estimate(session, order_id, reason)
    rma = session.new_rma()
    return {
        "order_id": order_id,
        "rma": rma,
        "reason": reason,
        "estimated_refund": estimate["estimated_refund"],
        "pickup_fee": estimate["pickup_fee"],
        "next_steps": "Our logistics partner will pick up the item within 48 hours. Keep "
                      "the item in its original packaging.",
    }


def cancel_order(session, order_id):
    """Attempt to cancel an order that is still within the free-cancel window."""
    order = data.get_order(order_id)
    if order is None:
        raise OrderNotFoundError(order_id)
    if not _owned(order, session):
        raise NotOwnedError(order_id)
    placed = datetime.fromisoformat(order["created"])
    elapsed_minutes = (datetime.now() - placed).total_seconds() / 60.0
    if order["status"] == "Cancelled":
        return {"order_id": order["order_id"], "cancelled": True, "note": "Order was already cancelled."}
    if order["status"] == "Processing" and elapsed_minutes <= 60:
        order["status"] = "Cancelled"
        return {"order_id": order["order_id"], "cancelled": True,
                "note": "Order cancelled. You will get an email confirmation and a refund "
                        "within %s." % data.REFUND_PROCESSING_DAYS}
    return {"order_id": order["order_id"], "cancelled": False,
            "note": kb.answer_for("cancellation")}


def search_products(session, query):
    """Keyword search over the product catalogue; returns up to 4 matches."""
    tokens = [t for t in query.lower().replace("/", " ").split() if len(t) > 2]
    results = []
    for sku, prod in data.PRODUCTS.items():
        haystack = (prod["name"] + " " + prod["category"] + " " + prod["description"]).lower()
        score = sum(1 for t in tokens if t in haystack)
        if score:
            results.append({"sku": sku, "name": prod["name"], "price": prod["price"],
                            "stock": prod["stock"], "rating": prod["rating"],
                            "score": score})
    results.sort(key=lambda r: (-r["score"], r["name"]))
    return results[:4]


def product_details(session, query):
    """Details for a specific product (matched by exact SKU or unique keyword)."""
    low = query.lower()
    sku_lookup = {k.lower(): k for k in data.PRODUCTS}
    sku = sku_lookup.get(low.strip())
    if sku:
        return {"matches": [{"sku": sku, "product": data.PRODUCTS[sku]}]}
    tokens = [t for t in low.split() if len(t) > 2]
    matches = []
    for s, prod in data.PRODUCTS.items():
        hay = (prod["name"] + " " + prod["category"] + " " + prod["description"]).lower()
        if any(t in hay for t in tokens):
            matches.append({"sku": s, "product": prod})
    return {"matches": matches[:3]}


def answer_policy(session, topic):
    """Return the policy / FAQ answer for the given topic key."""
    answer = kb.answer_for(topic)
    if answer is None:
        raise NotAllowedError("No policy entry matches topic: %s" % topic)
    return {"topic": topic, "answer": answer}


def escalate_to_human(session, issue, order_id=None):
    """Escalate to a human agent; creates a support ticket."""
    ticket = session.new_ticket()
    order_ref = order_id or session.recent_order()
    session.tickets.append(ticket)
    return {"ticket": ticket, "order_id": order_ref,
            "note": "A support specialist will reach out within 24 hours with updates "
                    "on your ticket."}


TOOLS = {
    t.name: t for t in [
        Tool("get_order_status", "Fetch the current status of an order by id", get_order_status),
        Tool("get_order_details", "Fetch items, totals, payment and dates of an order by id", get_order_details),
        Tool("track_shipment", "Stream tracking events and delivery ETA for a shipped order", track_shipment),
        Tool("check_return_eligibility", "Check if an order can be returned under the 30-day policy", check_return_eligibility),
        Tool("refund_estimate", "Estimate the refund amount a return would generate", refund_estimate),
        Tool("initiate_return", "File the return (RMA) once eligibility and reason are confirmed", initiate_return),
        Tool("cancel_order", "Cancel an order still inside the free-cancel window", cancel_order),
        Tool("search_products", "Keyword search over the product catalogue", search_products),
        Tool("product_details", "Fetch accurate details for one product (by SKU or keyword)", product_details),
        Tool("answer_policy", "Answer a question using the store policy knowledge base", answer_policy),
        Tool("escalate_to_human", "Raise a ticket so a human agent takes over", escalate_to_human),
    ]
}


def run_tool(name, session, **kwargs):
    """Execute a tool by name, raising its own exceptions on failure."""
    tool = TOOLS.get(name)
    if tool is None:
        raise NotAllowedError("Unknown tool: %s" % name)
    return tool.fn(session, **kwargs)