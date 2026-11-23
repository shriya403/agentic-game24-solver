"""A bounded contextual follow-up over the LangGraph thread checkpoint."""
from __future__ import annotations

import re


UNKNOWN = "I don't know: there is no relevant prior turn in this thread."


def contextual_followup(state, question, without_memory=False):
    """Answer questions about a previously completed turn, never infer missing history."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Provide a nonempty follow-up question")
    history = [] if without_memory else (state or {}).get("history", [])
    if not history:
        return {"answer": UNKNOWN, "memory_used": False, "previous_turns": 0}
    last = history[-1]
    words = set(re.findall(r"[a-z]+", question.lower()))
    if words & {"puzzle", "cards", "numbers", "inputs"}:
        answer = "Previous puzzle cards: " + ", ".join(map(str, last["puzzle"]))
    elif words & {"expression", "formula", "answer", "solution"}:
        expression = last.get("expression")
        answer = ("Previous expression: " + expression) if expression else UNKNOWN
    elif words & {"result", "status", "verified", "successful"}:
        answer = "Previous run status: " + last.get("status", "unknown")
    else:
        answer = "I don't know: this follow-up is outside the saved puzzle facts."
    return {"answer": answer, "memory_used": answer != UNKNOWN and not answer.startswith("I don't know"),
            "previous_turns": len(history)}
