"""Conversational memory for a single support session.

Keeps the raw history, the order ids the customer has mentioned (short-term
memory used for follow-up resolution like "what about *it*?"), the current
name/context bits and any pending multi-step action the agent started but has
not yet confirmed (e.g. "I checked your return eligibility - should I file it?").
"""


class Session:
    def __init__(self, customer_id="CUST-1001"):
        self.customer_id = customer_id
        self.history = []            # chat turns, {"role": ..., "content": ...}
        self.known_order_ids = []    # order ids seen in this conversation
        self.pending_action = None   # {"type": ..., "order_id": ..., "reason": ...}
        self.tickets = []            # escalated tickets created
        self.next_rma = 1001
        self.next_ticket = 1001

    def remember_order(self, order_id):
        if order_id and order_id not in self.known_order_ids:
            self.known_order_ids.append(order_id)

    def recent_order(self):
        """Most recently discussed order, or None."""
        return self.known_order_ids[-1] if self.known_order_ids else None

    def add_turn(self, role, content):
        self.history.append({"role": role, "content": content})

    def new_rma(self):
        value = "RMA-" + str(self.next_rma)
        self.next_rma += 1
        return value

    def new_ticket(self):
        value = "TKT-" + str(self.next_ticket)
        self.next_ticket += 1
        return value

    def summary(self):
        """Compact view of what the agent remembers (for UI / traces)."""
        return {
            "customer_id": self.customer_id,
            "orders": list(self.known_order_ids),
            "pending": self.pending_action,
            "tickets": list(self.tickets),
        }