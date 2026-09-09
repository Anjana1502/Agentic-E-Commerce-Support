"""The agent controller.

A lightweight ReAct-style loop: the agent
  1. reads the user message + memory -> picks an intent,
  2. plans a sequence of tool calls,
  3. executes them, capturing a trace of every call,
  4. composes an answer from the tool outputs,
  5. reflects (self-checks the outcome and adds follow-up suggestions),
  6. records the turn into conversational memory.

Intent detection and answering are rule-based so the demo is fully offline and
deterministic. Swapping the planner/responder for an LLM that picks from the
same :data:`tools.TOOLS` registry (function-calling) is described in the README.
"""

import re

from . import data, kb
from .memory import Session
from .tools import NotOwnedError, OrderNotFoundError, TOOLS, ToolError, run_tool

ORDER_RE = re.compile(r"\bORD[- ]?(\d{3,})\b", re.I)
SKU_RE = re.compile(r"\bSKU[- ]?(\d{3,})\b", re.I)
ESCALATE_RE = re.compile(r"\b(human|agent|manager|complaint|talk to|speak to|support|customer care|call)\b", re.I)
GREET_RE = re.compile(r"^\s*(hi|hello|hey|namaste|good (morning|afternoon|evening))\b", re.I)
THANKS_RE = re.compile(r"\b(thanks|thank you|thankyou|thx|appreciate)\b", re.I)
BYE_RE = re.compile(r"\b(bye|goodbye|good bye|see you|tata)\b", re.I)
CANCEL_RE = re.compile(r"\bcancel|\bnot needed", re.I)
RETURN_RE = re.compile(r"\breturn|\brefund|\bmoney back|\breplace|\bexchange", re.I)
TRACK_RE = re.compile(r"\btrack|\bwhere is my|\bstatus|\bdelivery|\bdelay|\barriv", re.I)
DETAILS_RE = re.compile(r"\bdetails|\bitems in my|\bwhat (was|did|did i|have) i|\bsummary", re.I)
PRODUCT_DETAILS_RE = re.compile(r"\b(more about|tell me about|info about|details of|about)\b", re.I)
PRODUCT_SEARCH_RE = re.compile(r"\b(buy|price|pricing|cost|find|looking for|recommend|suggest|want( to)? (buy|order|get)|show|search|catalog|catalogue|how much is|price of)\b", re.I)
CONFIRM_RE = re.compile(r"^\s*(yes|yep|yeah|sure|please|go ahead|ok|okay|do it|confirm|initiate|file it|start)\b|^\s*(yes|sure|please|ok|okay),", re.I)
DEFECTIVE_RE = re.compile(r"\b(defect|damage|broken|not working|fault|faulty|wrong item|different)\b", re.I)
HELP_RE = re.compile(r"\bhelp\b|\bwhat can you do\b|\bcapabilit", re.I)
POLICY_RE = re.compile(r"\bpolicy\b|\bhow (long|many|much)\b|\brules?\b|\btimeframe\b")


def _r(value):
    """Render a price like 1750.0 as 'Rs.1750'."""
    return "Rs." + ("%g" % value)


class Agent:
    def __init__(self):
        self.tools = {name: t.description for name, t in TOOLS.items()}

    def chat(self, raw_message, session=None):
        """Process one user message; return {"reply", "trace", "intent"} and update memory."""
        session = session or Session()
        message = raw_message.strip()
        session.add_turn("user", message)

        intent, trace = self._run(message, session)
        reply = self._respond(intent, message, session, trace)

        session.add_turn("assistant", reply)
        return {"reply": reply, "trace": trace, "intent": intent["name"], "memory": session.summary()}

    def _run(self, message, session):
        """Plan and execute tool calls for the detected intent."""
        low = message.lower()
        trace = []

        if ESCALATE_RE.search(message):
            return self._plan_escalate(message, session, trace), trace
        if GREET_RE.search(low):
            return {"name": "greeting"}, trace
        if BYE_RE.search(low):
            return {"name": "bye"}, trace
        if THANKS_RE.search(low):
            return {"name": "thanks"}, trace

        order_hit = ORDER_RE.search(message)
        if not order_hit and re.search(r"\b(how long|delivery time|delivery takes|how much|shipping charge|shipping fee|delivery charge|charge|fee)\b", low):
            topic = kb.infer_topic(low)
            if topic:
                return {"name": "policy", "topic": topic}, trace
        if CANCEL_RE.search(low):
            return self._plan_cancel(message, session, order_hit, trace), trace
        if RETURN_RE.search(low) and not POLICY_RE.search(message):
            return self._plan_return(message, session, order_hit, trace), trace
        if TRACK_RE.search(low):
            return self._plan_status(message, session, order_hit, trace), trace
        if DETAILS_RE.search(low):
            return self._plan_details(message, session, order_hit, trace), trace

        if session.pending_action and session.pending_action["type"] == "return" and CONFIRM_RE.match(message):
            return self._plan_return(message, session, order_hit, trace), trace

        topic = kb.infer_topic(low)
        if topic:
            return {"name": "policy", "topic": topic}, trace
        if SKU_RE.search(message) or PRODUCT_DETAILS_RE.search(low):
            return self._plan_product_details(message, session, trace), trace
        if PRODUCT_SEARCH_RE.search(low):
            return self._plan_product_search(message, session, trace), trace
        if HELP_RE.search(message):
            return {"name": "help"}, trace
        return {"name": "fallback"}, trace

    def _tool(self, session, trace, name, **kwargs):
        try:
            result = run_tool(name, session, **kwargs)
            trace.append({"tool": name, "args": kwargs, "ok": True,
                          "result": self._compact(result)})
            return result
        except ToolError as exc:
            trace.append({"tool": name, "args": kwargs, "ok": False,
                          "error": str(exc)})
            raise

    def _resolve_order(self, session, order_hit, message):
        """Return (kind, order_id) where kind in {id, memory, foreign, notfound, none}."""
        if order_hit:
            oid = "ORD-" + order_hit.group(1)
            order = data.get_order(oid)
            if order and order["customer_id"] != session.customer_id:
                return ("foreign", oid)
            session.remember_order(oid)
            return ("id", oid)
        if re.search(r"\b(it|that|this)\b", message, re.I) or "order" in message.lower():
            recent = session.recent_order()
            if recent:
                return ("memory", recent)
        return ("none", None)

    # ----- planning helpers -------------------------------------------------

    def _plan_status(self, message, session, order_hit, trace):
        kind, oid = self._resolve_order(session, order_hit, message)
        if kind == "foreign":
            return {"name": "status", "kind": "foreign", "order_id": oid}
        if kind == "none":
            return {"name": "status", "kind": "need_order"}
        try:
            result = self._tool(session, trace, "get_order_status", order_id=oid)
            if result["status"] == "Shipped":
                track = self._tool(session, trace, "track_shipment", order_id=oid)
            else:
                track = None
            return {"name": "status", "kind": "ok", "result": result, "track": track, "order_id": oid}
        except OrderNotFoundError:
            return {"name": "status", "kind": "notfound", "order_id": oid}

    def _plan_details(self, message, session, order_hit, trace):
        kind, oid = self._resolve_order(session, order_hit, message)
        if kind == "foreign":
            return {"name": "details", "kind": "foreign", "order_id": oid}
        if kind == "none":
            return {"name": "details", "kind": "need_order"}
        try:
            result = self._tool(session, trace, "get_order_details", order_id=oid)
            return {"name": "details", "kind": "ok", "result": result, "order_id": oid}
        except OrderNotFoundError:
            return {"name": "details", "kind": "notfound", "order_id": oid}

    def _plan_cancel(self, message, session, order_hit, trace):
        kind, oid = self._resolve_order(session, order_hit, message)
        if kind == "foreign":
            return {"name": "cancel", "kind": "foreign", "order_id": oid}
        if kind == "none":
            return {"name": "cancel", "kind": "need_order"}
        try:
            result = self._tool(session, trace, "cancel_order", order_id=oid)
            return {"name": "cancel", "kind": "ok", "result": result, "order_id": oid}
        except OrderNotFoundError:
            return {"name": "cancel", "kind": "notfound", "order_id": oid}

    def _plan_return(self, message, session, order_hit, trace):
        kind, oid = self._resolve_order(session, order_hit, message)
        if kind == "foreign":
            return {"name": "return", "kind": "foreign", "order_id": oid}

        pending = session.pending_action
        is_confirm = bool(CONFIRM_RE.match(message))

        if pending and pending["type"] == "return" and is_confirm:
            if oid is None or oid == pending["order_id"]:
                oid = pending["order_id"]
                try:
                    result = self._tool(session, trace, "initiate_return",
                                        order_id=oid, reason=pending["reason"])
                    session.pending_action = None
                    return {"name": "return", "kind": "initiated", "result": result, "order_id": oid}
                except (NotOwnedError, OrderNotFoundError):
                    return {"name": "return", "kind": "error"}

        if oid is None:
            return {"name": "return", "kind": "need_order"}

        try:
            eligibility = self._tool(session, trace, "check_return_eligibility", order_id=oid)
        except (OrderNotFoundError, NotOwnedError):
            return {"name": "return", "kind": "notfound", "order_id": oid}

        if not eligibility["eligible"]:
            return {"name": "return", "kind": "ineligible", "result": eligibility, "order_id": oid}

        reason = self._detect_reason(message)
        estimate = self._tool(session, trace, "refund_estimate", order_id=oid, reason=reason)
        session.pending_action = {"type": "return", "order_id": oid, "reason": reason}
        return {"name": "return", "kind": "confirm", "result": eligibility,
                "estimate": estimate, "reason": reason, "order_id": oid}

    def _plan_product_search(self, message, session, trace):
        try:
            results = self._tool(session, trace, "search_products", query=message)
        except ToolError:
            results = {}
        return {"name": "product_search", "kind": "ok", "results": results, "query": message}

    def _plan_product_details(self, message, session, trace):
        sku_hit = SKU_RE.search(message)
        query = ("SKU-" + sku_hit.group(1)) if sku_hit else message
        try:
            result = self._tool(session, trace, "product_details", query=query)
        except ToolError:
            result = {"matches": []}
        return {"name": "product_details", "kind": "ok", "result": result, "query": query}

    def _plan_escalate(self, message, session, trace):
        order_hit = ORDER_RE.search(message)
        if order_hit:
            oid = "ORD-" + order_hit.group(1)
        else:
            oid = session.recent_order()
        result = self._tool(session, trace, "escalate_to_human", issue=message, order_id=oid)
        return {"name": "escalate", "kind": "ok", "result": result}

    # ----- responders -------------------------------------------------------

    def _respond(self, intent, message, session, trace):
        kind = intent.get("name")
        responder = getattr(self, "_answer_" + kind, self._answer_fallback)
        return responder(intent, message, session)

    def _answer_greeting(self, intent, message, session):
        name = data.CUSTOMERS.get(session.customer_id, {}).get("name", "there")
        return (
            f"Hi {name}! I'm your support assistant. I can help you with\n"
            "\u2022 Order status & tracking\n"
            "\u2022 Returns & refunds\n"
            "\u2022 Order cancellations\n"
            "\u2022 Product lookup\n"
            "\u2022 Store policies (shipping, warranty, payments)\n"
            "Just tell me your ORDER number (e.g. ORD-1025) and what you need. "
            "You can also say 'talk to a human' at any time."
        )

    def _answer_thanks(self, intent, message, session):
        return "You're welcome! Is there anything else I can help you with?"

    def _answer_bye(self, intent, message, session):
        return "Thanks for reaching out. Have a great day! If you need anything, I'm a message away."

    def _answer_help(self, intent, message, session):
        return (
            "Here's everything I can do:\n"
            "\u2022 \"What's the status of ORD-1025?\" - order status\n"
            "\u2022 \"Track ORD-1024\" - shipment tracking + ETA\n"
            "\u2022 \"I want to return ORD-1026\" - return/refund flow\n"
            "\u2022 \"Cancel ORD-1025\" - cancellation policy\n"
            "\u2022 \"Show me wireless headphones\" - product search\n"
            "\u2022 \"What's your return policy?\" - policy answers\n"
            "\u2022 \"Talk to a human\" - escalate to a specialist"
        )

    def _answer_fallback(self, intent, message, session):
        recent = session.recent_order()
        hint = f" Also, if you meant your order {recent}, just say so and I'll look it up." if recent else ""
        return (
            "I didn't quite catch that. I can check order status, tracking, returns, "
            "cancellations, products or policies - try phrasing it like the examples above."
            + hint
        )

    def _answer_status(self, intent, message, session):
        kind = intent["kind"]
        if kind == "foreign":
            return self._refuse_foreign(intent["order_id"])
        if kind == "need_order":
            return "I'd need your ORDER number to check that. It looks like ORD- followed by 4 digits, e.g. ORD-1025."
        if kind == "notfound":
            return (
                f"I couldn't find order {intent['order_id']}. Double-check the number - "
                "it should appear in your order confirmation email. (Alternatively, reply "
                "'talk to a human' and a specialist will trace it for you.)"
            )
        result, track = intent["result"], intent["track"]
        oid = result["order_id"]
        items = ", ".join(session_history_items(session, oid)) or "your items"
        base = ({
            "Shipped": f"Your order {oid} is on its way! Latest update ({result['event_date']}): {result['latest_event']}.",
            "Delivered": f"Your order {oid} has been delivered ({result['event_date']}).",
            "Processing": f"Your order {oid} is being processed in our warehouse.",
            "Cancelled": f"Your order {oid} was cancelled and the refund has been initiated.",
        }.get(result["status"], f"Your order {oid} is {result['status']}."))
        if track is not None:
            events = "\n".join(f"  {d}: {t}" for d, t in track["events"])
            eta = f"\nExpected delivery: {track['eta']}." if track.get("eta") else ""
            base += f"\nTracking trail:\n{events}{eta}"
        elif result["status"] == "Processing":
            base += "\nYou'll receive a tracking link by email once it ships."
        base += f"\nItems in this order: {items}."
        return base

    def _answer_details(self, intent, message, session):
        kind = intent["kind"]
        if kind == "foreign":
            return self._refuse_foreign(intent["order_id"])
        if kind == "need_order":
            return "Which order would you like the details for? Share the ORDER number (e.g. ORD-1025)."
        if kind == "notfound":
            return f"I couldn't find order {intent['order_id']}. Can you double-check the number?"
        r = intent["result"]
        lines = [f"Order {r['order_id']} - {r['status']}",
                 f"Placed on {r['created']} \u00b7 Paid via {r['payment']}"]
        for it in r["items"]:
            lines.append(f"  - {it['name']} ({it['sku']}) x{it['qty']} - {_r(it['price'])}")
        lines.append(f"Total: {_r(r['total'])}")
        return "\n".join(lines)

    def _answer_cancel(self, intent, message, session):
        kind = intent["kind"]
        if kind == "foreign":
            return self._refuse_foreign(intent["order_id"])
        if kind == "need_order":
            return "Which order do you want to cancel? I just need the ORDER number (e.g. ORD-1025)."
        if kind == "notfound":
            return f"Couldn't find order {intent['order_id']}. Please re-check the number."
        r = intent["result"]
        if r["cancelled"]:
            session.pending_action = None
            return f"Done - {r['note']}"
        return (
            "I checked and this order can't be cancelled right now (free cancellation only "
            "applies within 60 minutes of placing, before the warehouse starts packing).\n\n"
            "You can return the items after delivery instead, within the 30-day window. "
            "Want me to check the return eligibility?"
        )

    def _answer_return(self, intent, message, session):
        kind = intent["kind"]
        oid = intent.get("order_id")
        if kind == "foreign":
            return self._refuse_foreign(oid)
        if kind == "need_order":
            return "I can help with returns/refunds! Which order would you like to return? (e.g. return ORD-1026)"
        if kind == "notfound":
            return f"I couldn't find order {oid}. Could you double-check the ORDER number?"
        if kind == "error":
            return "Something went wrong filing that return. Could you tell me the order number again?"
        if kind == "ineligible":
            return self._reflect_ineligible(intent)
        if kind == "initiated":
            r = intent["result"]
            return (
                f"Return filed! Here are your details:\n"
                f"  Return ID (RMA): {r['rma']}\n"
                f"  Order: {r['order_id']}\n"
                f"  Reason: {r['reason']}\n"
                f"  Estimated refund: {_r(r['estimated_refund'])}\n"
                f"{r['next_steps']}\n\n"
                f"Refunds are disbursed within 5-7 business days after pickup. Anything else?"
            )
        est = intent["estimate"]
        return (
            f"Good news - order {oid} is within the 30-day return window.\n\n"
            f"Estimated refund: {_r(est['estimated_refund'])} "
            f"(item total {_r(est['item_total'])} minus a {_r(est['pickup_fee'])} pickup fee).\n\n"
            f"Reason I noted: '{intent['reason']}'. Should I go ahead and file the return? "
            f"Just say \"yes\"."
        )

    def _reflect_ineligible(self, intent):
        reason = intent["result"]["reason"]
        if any(w in reason for w in ("window", "beyond", "extended", "ended")):
            return (
                f"{reason.capitalize()}\n\n"
                "The return window has closed for this item. For products with a "
                "manufacturing defect you can still raise a warranty claim - just "
                "describe the problem and I'll file it. Anything else I can help with?"
            )
        return (
            f"{reason}\n\n"
            "I can't file this return yet, but happy to help with tracking, another "
            "order, or escalating to a specialist."
        )

    def _answer_product_search(self, intent, message, session):
        results = intent["results"]
        if not results:
            return (
                "I searched the catalogue but didn't find a match for that.\n\n"
                "Popular searches: headphones, earbuds, smart watch, backpack, yoga mat, "
                "sunglasses, vacuum, water bottle, lamp, travel organizer. Try rephrasing "
                "with one of those, or ask \"show me <category>\"."
            )
        lines = ["Here's what I found:"]
        for r in results:
            lines.append(
                f"  \u2022 {r['name']} ({r['sku']}) - {_r(r['price'])} \u00b7 {r['stock']} in stock \u00b7 \u2605 {r['rating']}"
            )
        lines.append("\nReply 'more about <SKU>' (e.g. 'more about SKU-101') for full details.")
        return "\n".join(lines)

    def _answer_product_details(self, intent, message, session):
        matches = intent["result"]["matches"]
        if not matches:
            return "I couldn't find a product for that. Try a category term like 'headphones' or 'vacuum'."
        if len(matches) > 1:
            lines = ["I found a few matches:"]
            for m in matches:
                p = m["product"]
                lines.append(f"  \u2022 {p['name']} ({m['sku']}) - {_r(p['price'])}")
            return "\n".join(lines) + "\n\nSay 'more about <SKU>' to see one in detail."
        m = matches[0]
        p = m["product"]
        return (
            f"{p['name']} ({m['sku']})\n"
            f"  Price: {_r(p['price'])} \u00b7 In stock: {p['stock']} \u00b7 Rating: {p['rating']}/5\n"
            f"  Category: {p['category']}\n"
            f"  {p['description']}"
        )

    def _answer_policy(self, intent, message, session):
        topic = intent.get("topic")
        answer = kb.answer_for(topic) if topic else None
        if not answer:
            return "I don't have a policy entry for that yet. Try return, refund, shipping, tracking, cancel, warranty, payment or account."
        return answer + "\n\nAnything else I can help with?"

    def _answer_escalate(self, intent, message, session):
        r = intent["result"]
        ref = f" Order {r['order_id']} has been attached for reference." if r["order_id"] else ""
        return (
            f"I've raised a ticket for you - {r['ticket']}.{ref}\n\n{r['note']}\n\n"
            "Meanwhile, is there anything I can help with while you wait?"
        )

    # ----- helpers ----------------------------------------------------------

    def _refuse_foreign(self, oid):
        return (
            f"For your privacy I can only access orders registered to your account - "
            f"{oid} isn't one of them. If this is your order, double-check the email it "
            "was placed under, or say 'talk to a human' for help."
        )

    def _detect_reason(self, message):
        if DEFECTIVE_RE.search(message):
            return "defective"
        return "changed my mind"

    @staticmethod
    def _compact(value, limit=120):
        text = str(value).replace("\n", " ")
        return text if len(text) <= limit else text[: limit - 3] + "..."


def session_history_items(session, order_id):
    """Helper: item names for an order, looked up from the data layer."""
    order = data.get_order(order_id)
    if not order:
        return []
    return [it["name"] for it in order["items"]]