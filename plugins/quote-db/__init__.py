"""Quote database plugin package."""
try:
    from .quote_db import QuoteDBPlugin
except ImportError:
    # For standalone test runs
    from quote_db import QuoteDBPlugin

__version__ = "1.0.0"
__all__ = ["QuoteDBPlugin"]
