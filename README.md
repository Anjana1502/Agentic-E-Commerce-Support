# Agentic AI - E-commerce Customer Support Assistant

A working **agentic AI** customer-support agent built for the **Naan Mudhalvan
IBM Agentic AI Internship**. It resolves real support requests - order status,
tracking, returns, refunds, cancellations, product lookup and store policies -
by *planning and executing tool calls*, keeping *conversational memory*, applying
*privacy guardrails* and *escalating to humans* when needed.

Everything is **standard Python with zero third-party dependencies**, so the
demo runs offline, anywhere, with no API keys or pip installs.

---

## 1. Quick start

```bash
# Web chat UI  (http://127.0.0.1:8000)
python ui\web.py          # or double-click run_demo.bat

# Terminal chat
python cli.py

# Run the test suite (14 tests, stdlib unittest)
python -m unittest tests.test_agent -v
```

> Use `py -3.12 ...` if `python` points to an older interpreter on your machine.

## 2. Try these prompts

| You type                                                        | Agent does                                              |
|-----------------------------------------------------------------|---------------------------------------------------------|
| `what is the status of ORD-1024?`                               | `get_order_status` + `track_shipment`, shows ETA        |
| `I want to return ORD-1026` → `yes`                             | 2-step return flow: eligibility → refund estimate → RMA |
| `I want to return ORD-1027`                                     | detects window closed → suggests warranty claim (reflection) |
| `cancel ORD-1025`                                               | checks cancellation policy → suggests return alternative |
| `show me wireless headphones` → `more about SKU-101`            | catalogue search → product details                      |
| `what is your return policy?` / `delivery time?`                | answers from the policy knowledge base                  |
| `track ORD-9001`                                                | **privacy guardrail** - refuses another customer's order |
| `talk to a human about ORD-1025`                                | creates a ticket and hands over                         |

To see *why* the agent answered that way, open the **"Agent steps"** panel under
each reply in the web UI (a full tool-call trace), or watch the `steps :` line
in the CLI.

## 3. What makes it *agentic*

The agent in `src/ecomagent/agent.py` implements a lightweight **ReAct-style loop**:

```
User message  →  intent + plan  →  tool calls (trace captured)
     →  compose answer  →  reflect / self-check  →  update memory
```

Concrete agentic capabilities demonstrated in the code:

* **Tools / function calling** - a declarative registry (`tools.py`) of 11 tools
  (`get_order_status`, `track_shipment`, `check_return_eligibility`,
  `refund_estimate`, `initiate_return`, `cancel_order`, `search_products`,
  `product_details`, `answer_policy`, `escalate_to_human`, ...).
* **Multi-step planning** - order status for a shipped order automatically calls
  *two* tools; a return automatically chains *eligibility → estimate → RMA*.
* **Tool failure handling** - unknown orders, not-your-account orders and
  not-yet-delivered returns are caught and explained naturally.
* **Conversational memory** (`memory.py`) - remembers discussed order ids so
  follow-ups like *"tell me the details for it"* resolve correctly; keeps a
  *pending action* to power two-step confirmation ("should I file the return? ... yes").
* **Reflection / self-correction** - if a return isn't possible, it *re-evaluates*
  and offers the warranty path or alternatives instead of dead-ending.
* **Guardrails** - account ownership checks block access to other customers'
  orders; no personal/OTP data is ever exposed (see `_refuse_foreign`).
* **Human hand-off** - escalation creates a tracking ticket, a core agentic AI
  pattern (memory of the ticket is kept in-session).

### Architecture

```
                     ┌─────────────────────────────┐
   User ─text──►     │         AGENT LOOP          │      ┌──────────────┐
              Web UI /│  detect intent (ReAct)      │──►   │  TOOL REGISTRY│
              CLI    │  plan ▸ execute ▸ respond    │ call  │  tools.py    │
                     │  reflect ▸ remember          │◄─────└──────┬───────┘
                     └──────────┬──────────────────┘             │
                                │ reads/writes                   ▼
                     ┌──────────▼──────────┐       ┌──────────────────────────┐
                     │  SESSION MEMORY     │       │  DATA + KNOWLEDGE BASE   │
                     │  memory.py          │       │  data.py  kb.py          │
                     └─────────────────────┘       └──────────────────────────┘
```

## 4. Project structure

```
agentic-ecommerce-support/
├── cli.py                     # terminal chat client
├── run_demo.bat               # one-click web demo launcher
├── requirements.txt           # none required (stdlib only)
├── ui/
│   ├── web.py                 # stdlib HTTP server + /api/chat endpoint
│   └── static/index.html      # chat UI with agent-step traces
├── src/ecomagent/
│   ├── agent.py               # ReAct agent: intent, planning, reflection, memory
│   ├── tools.py               # tool registry (11 tools) + mock backend calls
│   ├── data.py                # mock orders, products, tracking events
│   ├── kb.py                  # policy knowledge base (returns, refunds, ...)
│   └── memory.py              # per-session memory + pending actions
└── tests/test_agent.py        # 14 end-to-end tests (stdlib unittest)
```

## 5. Design decisions & how to take it to production

* **Behaviours are driven by the tool registry, not hard-coded answers.** The
  responder only reads tool output. To swap the rule-based *planner* for an LLM
  with function calling (IBM watsonx / OpenAI / LangChain), point the model at
  `Tool.name` + `Tool.description` and let it emit the same tool calls - the
  registry, memory and UI stay untouched.
* **Mock data lives only in `data.py`.** Replace it with your ERP / order
  database connection and the merchant product feed; every other layer is
  database-agnostic.
* **Deterministic by design.** The current planner needs no LLM, so the demo is
  repeatable and can be evaluated offline. The conversational confirm, reflection
  and escalation patterns are the same ones a model-backed agent would follow.

## 6. Sample conversation (script for your demo)

```
User  : what is the status of ORD-1024?
Agent : Your order ORD-1024 is on its way! Latest update (2026-09-08): Out for delivery.
        Tracking trail:
          2026-08-21: Order accepted
          2026-08-22: Shipment picked up from our fulfilment centre
          2026-08-24: In transit - Hub, Chennai
          2026-09-08: Out for delivery
        Expected delivery: 2026-09-10.
        Items in this order: Dolby Wireless Headphones, Pro Yoga Mat.

User  : I want to return ORD-1026
Agent : Good news - order ORD-1026 is within the 30-day return window.
        Estimated refund: Rs.1750 (item total Rs.1799 minus a Rs.49 pickup fee).
        Reason I noted: 'changed my mind'. Should I go ahead and file the return? Just say "yes".

User  : yes
Agent : Return filed! Return ID (RMA): RMA-1001  Order: ORD-1026
        Our logistics partner will pick up the item within 48 hours. ...

User  : track ORD-9001
Agent : For your privacy I can only access orders registered to your account -
        ORD-9001 isn't one of them. ...
```

## 7. Demo order data

`ORD-1024` Shipped (headphones + yoga mat) · `ORD-1025` Processing (smart watch) ·
`ORD-1026` Delivered, returnable (backpack) · `ORD-1027` Delivered, window expired
(sunglasses) · `ORD-1028` Cancelled (lamp) · `ORD-9001` belongs to *another*
customer (for the privacy-guardrail demo).

---

Built for the Naan Mudhalvan IBM Agentic AI Internship. Core concepts mapped to
the module: **Agents, Tools & Function Calling, Memory, Planning, Reflection,
Guardrails and Human Hand-off.**