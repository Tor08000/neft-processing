def summarize(t: str) -> str:
    return t[:200] + ('...' if len(t) > 200 else '')
