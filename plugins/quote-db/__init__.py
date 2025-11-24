"""Quote database plugin package."""
try:
    from .quote_db import QuoteDBPlugin
except ImportError:
    # Handle case when run as script or in pytest without proper package setup
    from quote_db import QuoteDBPlugin

__version__ = "1.0.0"
__all__ = ["QuoteDBPlugin"]
