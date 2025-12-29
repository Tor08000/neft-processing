def build_unified_explain(*args, **kwargs):
    from app.services.explain.unified import build_unified_explain as _build_unified_explain

    return _build_unified_explain(*args, **kwargs)


__all__ = ["build_unified_explain"]
