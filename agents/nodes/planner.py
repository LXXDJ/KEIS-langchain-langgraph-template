"""Planning helpers for future deep/custom graphs."""

from __future__ import annotations


def make_plan(user_input: str) -> list[str]:
    return [
        f"Understand request: {user_input}",
        "Collect needed context",
        "Draft and refine answer",
    ]
