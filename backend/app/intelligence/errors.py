class IntelligenceError(Exception):
    """Base class. Callers catch this and fall back to rules with a visible reason."""


class NotConfigured(IntelligenceError):
    pass


class BudgetExceeded(IntelligenceError):
    pass


class UpstreamError(IntelligenceError):
    pass
