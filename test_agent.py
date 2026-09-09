"""End-to-end tests for the agent.

Run with:  python -m unittest tests.test_agent -v
(uses only the standard library, no pytest needed)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from ecomagent.agent import Agent
from ecomagent.memory import Session


class AgentTestCase(unittest.TestCase):
    def setUp(self):
        self.agent = Agent()
        self.session = Session("CUST-1001")

    def chat(self, message):
        return self.agent.chat(message, self.session)

    def tool_names(self, result):
        return [t["tool"] for t in result["trace"]]

    def test_greeting(self):
        out = self.chat("hi")
        self.assertEqual(out["intent"], "greeting")
        self.assertIn("Anjana", out["reply"])

    def test_order_status_shipped_uses_two_tools(self):
        out = self.chat("what is the status of ORD-1024?")
        self.assertEqual(out["intent"], "status")
        self.assertEqual(self.tool_names(out), ["get_order_status", "track_shipment"])
        self.assertIn("Out for delivery", out["reply"])
        self.assertIn("2026-09-10", out["reply"])

    def test_order_status_asks_for_id_without_one(self):
        out = self.chat("where is my order?")
        self.assertEqual(out["intent"], "status")
        self.assertIn("ORDER number", out["reply"])

    def test_privacy_guardrail_for_foreign_order(self):
        out = self.chat("track ORD-9001")
        self.assertEqual(out["intent"], "status")
        self.assertIn("privacy", out["reply"])
        self.assertIn("ORD-9001", out["reply"])

    def test_return_confirm_flow_two_turn(self):
        first = self.chat("i want to return ORD-1026")
        self.assertEqual(first["intent"], "return")
        self.assertEqual(self.tool_names(first), ["check_return_eligibility", "refund_estimate"])
        self.assertIn("within the 30-day return window", first["reply"])
        self.assertIn("Rs.1750", first["reply"])
        second = self.chat("yes")
        self.assertEqual(second["intent"], "return")
        self.assertEqual(self.tool_names(second), ["initiate_return"])
        self.assertIn("RMA-", second["reply"])
        self.assertIsNone(self.session.pending_action)

    def test_return_out_of_window_reflected(self):
        out = self.chat("I want to return ORD-1027")
        self.assertEqual(out["intent"], "return")
        self.assertIn("window", out["reply"].lower())
        self.assertIn("warranty", out["reply"].lower())

    def test_cancel_too_late_suggests_return(self):
        out = self.chat("cancel ORD-1025")
        self.assertEqual(out["intent"], "cancel")
        self.assertIn("can't be cancelled", out["reply"])
        self.assertIn("return", out["reply"])

    def test_product_search(self):
        out = self.chat("show me wireless headphones")
        self.assertEqual(out["intent"], "product_search")
        self.assertIn("SKU-101", out["reply"])
        self.assertIn("Rs.2499", out["reply"])

    def test_product_details_by_sku(self):
        out = self.chat("more about SKU-101")
        self.assertEqual(out["intent"], "product_details")
        self.assertIn("Dolby Wireless Headphones", out["reply"])
        self.assertEqual(self.tool_names(out), ["product_details"])

    def test_policy_question(self):
        out = self.chat("what is your return policy?")
        self.assertEqual(out["intent"], "policy")
        self.assertTrue(out["trace"] == [])  # answered straight from the KB
        self.assertIn("30 days", out["reply"])

    def test_shipping_policy_question(self):
        out = self.chat("what is the delivery time?")
        self.assertEqual(out["intent"], "policy")
        self.assertIn("5-7 business days", out["reply"])

    def test_escalate_creates_ticket(self):
        out = self.chat("I want to talk to a human about ORD-1025")
        self.assertEqual(out["intent"], "escalate")
        self.assertEqual(self.tool_names(out), ["escalate_to_human"])
        self.assertIn("TKT-1001", out["reply"])
        self.assertIn("TKT-1001", self.session.tickets)

    def test_memory_resolves_follow_up(self):
        self.chat("what is the status of ORD-1025?")
        out = self.chat("tell me the details for it")
        self.assertEqual(out["intent"], "details")
        self.assertIn("Pulse Smart Watch", out["reply"])

    def test_unknown_message_falls_back(self):
        out = self.chat("sing me a song")
        self.assertEqual(out["intent"], "fallback")
        self.assertIn("didn't quite catch", out["reply"])


if __name__ == "__main__":
    unittest.main(verbosity=2)