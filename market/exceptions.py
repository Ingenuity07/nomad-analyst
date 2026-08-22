class MarketDataError(Exception):
    """Base exception for all market data subsystem errors."""
    pass

class ProviderConnectionError(MarketDataError):
    """Raised when the provider is unavailable or connection times out."""
    pass

class RateLimitExceededError(MarketDataError):
    """Raised when the provider API rate limits are exceeded."""
    pass

class SymbolNotFoundError(MarketDataError):
    """Raised when a symbol does not exist on the target exchanges."""
    pass

class InvalidPayloadError(MarketDataError):
    """Raised when the provider payload is corrupt, malformed, or fails validation."""
    pass

class AuthenticationError(MarketDataError):
    """Raised when provider authentication fails (e.g. invalid keys)."""
    pass
