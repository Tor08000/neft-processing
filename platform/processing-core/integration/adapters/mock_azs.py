"""Simple adapter simulator for AZS partners."""
from __future__ import annotations

import random
import time
from typing import Callable

from httpx import Client


class MockAZSAdapter:
    """Generate and submit synthetic fuel transactions to the intake API."""

    def __init__(self, client: Client, partner_id: str, token: str, terminal_id: str, card_id: str):
        self.client = client
        self.partner_id = partner_id
        self.token = token
        self.terminal_id = terminal_id
        self.card_id = card_id

    def _headers(self) -> dict[str, str]:
        return {"x-partner-token": self.token}

    def authorize(self, amount: int, liters: float | None = None) -> dict:
        payload = {
            "external_partner_id": self.partner_id,
            "terminal_id": self.terminal_id,
            "amount": amount,
            "liters": liters,
            "card_identifier": self.card_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        response = self.client.post("/api/v1/intake/authorize", json=payload, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def run_load(self, count: int = 10, amount_generator: Callable[[], int] | None = None) -> list[dict]:
        amount_generator = amount_generator or (lambda: random.randint(100, 1000))
        results: list[dict] = []
        for _ in range(count):
            results.append(self.authorize(amount_generator()))
        return results
