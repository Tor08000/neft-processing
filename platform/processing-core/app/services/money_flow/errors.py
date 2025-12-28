class MoneyFlowError(Exception):
    """Base error for money flow failures."""


class MoneyFlowTransitionError(MoneyFlowError):
    """Raised when a state transition is not allowed."""


class MoneyFlowNotFound(MoneyFlowError):
    """Raised when a money flow cannot be located."""
