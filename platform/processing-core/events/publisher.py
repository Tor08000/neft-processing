"""Event publisher stub for domain events."""


def publish(event_name: str, payload: dict) -> None:
    """Send an event to the configured broker.

    This placeholder keeps the interface stable while the transport
    implementation is designed.
    """
    del event_name, payload
