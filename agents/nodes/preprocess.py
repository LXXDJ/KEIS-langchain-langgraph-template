"""Preprocessing hooks for future custom graph composition."""

from __future__ import annotations


def preprocess_input(user_input: str) -> str:
    return user_input.strip()
