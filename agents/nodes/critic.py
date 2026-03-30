"""Output review helpers for future custom graph composition."""

from __future__ import annotations

from typing import Any


def review_output(output: str) -> dict[str, Any]:
    return {
        "reviewed": True,
        "length": len(output),
    }
