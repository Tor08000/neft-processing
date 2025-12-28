class UnifiedExplainError(Exception):
    pass


class UnifiedExplainNotFound(UnifiedExplainError):
    pass


class UnifiedExplainValidationError(UnifiedExplainError):
    pass


__all__ = ["UnifiedExplainError", "UnifiedExplainNotFound", "UnifiedExplainValidationError"]
