"""Knowledge base of store policies and common questions.

Used by the `answer_policy` tool. Topic inference is keyword based so the whole
demo runs without any external LLM API. In production this would be backed by a
semantic / vector-search index of policy documents.
"""

from . import data

RETURN_POLICY = (
    "You can return most items within 30 days of delivery in their original "
    "condition with tags intact. Return shipping is FREE if the item is "
    "defective or damaged; otherwise a Rs.50 pickup fee is deducted from the "
    "refund. Groceries and personalised items are non-returnable."
)

REFUND_POLICY = (
    "Refunds are processed to the original payment method within "
    + data.REFUND_PROCESSING_DAYS
    + " after the returned item reaches our warehouse. Once it clears, you "
    "will get an email and the amount is released within 1-2 working days."
)

SHIPPING_POLICY = (
    "Standard delivery takes 5-7 business days. Express delivery is available "
    "in 2-3 business days. Shipping is FREE on orders above Rs."
    + str(int(data.FREE_SHIPPING_MIN))
    + "; otherwise a flat Rs."
    + str(int(data.SHIPPING_FEE))
    + " fee applies."
)

TRACKING_POLICY = (
    "You can track your shipment in two ways: ask me with your ORDER number "
    "and I will check it live, or use the 'Track Order' link in your order "
    "confirmation email / the 'My Orders' page on the app."
)

CANCEL_POLICY = (
    "Orders can be cancelled free of charge within 60 minutes of placing them, "
    "as long as they have not moved to 'Processing'. Once the warehouse starts "
    "preparing the shipment, cancellation is no longer possible and the best "
    "option is a return after delivery."
)

WARRANTY_POLICY = (
    "Electronic items carry a " + data.WARRANTY_DURATION + " against manufacturing "
    "defects. To raise a warranty claim, share your ORDER number and describe "
    "the fault - I will file a claim and arrange a pickup."
)

PAYMENT_POLICY = (
    "We accept UPI, credit/debit cards, net banking, PayPal and Cash on "
    "Delivery (on eligible pincodes). EMIs of 3, 6 and 9 months are available "
    "on orders above Rs.3000."
)

ACCOUNT_POLICY = (
    "For password reset, order history or saved addresses, go to 'My Account'. "
    "An OTP will be sent to your registered mobile/email to verify your identity."
)

FAQ = {
    "returns": {
        "keywords": ["return", "replace", "exchange", "send it back", "not as expected"],
        "answer": RETURN_POLICY,
    },
    "refunds": {
        "keywords": ["refund", "money back", "reversal", "credit", "reimburs"],
        "answer": REFUND_POLICY,
    },
    "shipping": {
        "keywords": ["shipping", "delivery charge", "shipping charge", "delivery time", "deliver", "express"],
        "answer": SHIPPING_POLICY,
    },
    "tracking": {
        "keywords": ["track", "where is my order", "where is my package", "shipment status", "transit"],
        "answer": TRACKING_POLICY,
    },
    "cancellation": {
        "keywords": ["cancel", "cancel order", "not needed"],
        "answer": CANCEL_POLICY,
    },
    "warranty": {
        "keywords": ["warranty", "claim", "broken", "not working", "defect", "repair"],
        "answer": WARRANTY_POLICY,
    },
    "payment": {
        "keywords": ["payment", "upi", "credit card", "debit card", "cod", "emi", "paypal", "net banking"],
        "answer": PAYMENT_POLICY,
    },
    "account": {
        "keywords": ["password", "account", "profile", "login", "sign in", "address"],
        "answer": ACCOUNT_POLICY,
    },
}


def infer_topic(message):
    """Return the best-matching FAQ topic for a message, or None."""
    low = message.lower()
    best_topic, best_hits = None, 0
    for topic, entry in FAQ.items():
        hits = sum(1 for kw in entry["keywords"] if kw in low)
        if hits > best_hits:
            best_topic, best_hits = topic, hits
    return best_topic


def answer_for(topic):
    """Return the canned answer for a topic key."""
    entry = FAQ.get(topic)
    return entry["answer"] if entry else None