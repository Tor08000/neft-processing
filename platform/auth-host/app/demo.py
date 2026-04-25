from __future__ import annotations

import os

DEMO_CLIENT_EMAIL = os.getenv("NEFT_DEMO_CLIENT_EMAIL", "client@neft.local")
DEMO_CLIENT_PASSWORD = os.getenv("NEFT_DEMO_CLIENT_PASSWORD", "Client123!")
DEMO_CLIENT_FULL_NAME = os.getenv("NEFT_DEMO_CLIENT_FULL_NAME", "Demo Client")
DEMO_CLIENT_UUID = os.getenv(
    "NEFT_DEMO_CLIENT_UUID", "00000000-0000-0000-0000-000000000001"
)
