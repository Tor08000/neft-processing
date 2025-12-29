def build_fleet_assistant(*args, **kwargs):
    from app.services.fleet_assistant.explain_bridge import build_fleet_assistant as _build_fleet_assistant

    return _build_fleet_assistant(*args, **kwargs)


__all__ = ["build_fleet_assistant"]
