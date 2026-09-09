"""Command-line chat client for the e-commerce support agent.

Run:  python cli.py
"""

import sys

sys.path.insert(0, "src")

from ecomagent.agent import Agent
from ecomagent.memory import Session

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


TRACE_CHARS = {True: "[ok] ", False: "[!] "}


def main():
    agent = Agent()
    session = Session()

    print("=" * 62)
    print("  Agentic AI - E-commerce Customer Support Assistant (demo)")
    print("  Type 'exit' to leave, or 'help' for example phrases.")
    print("=" * 62)
    print()

    while True:
        try:
            user = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user.lower() in {"exit", "quit", "exit()"}:
            print("agent > Goodbye!")
            break

        result = agent.chat(user, session)

        if result["trace"]:
            print("steps : " + " -> ".join(
                f"{TRACE_CHARS[t['ok']]}{t['tool']}" for t in result["trace"]
            ))
        print("agent > " + result["reply"])
        print()


if __name__ == "__main__":
    main()