"""Quote database plugin package."""
try:
    # When imported as a package (from plugins.quote-db)
    from .quote_db import QuoteDBPlugin
except ImportError:
    # When imported directly (from quote_db in tests)
    from quote_db import QuoteDBPlugin  # type: ignore[no-redef]

__version__ = "1.0.0"
__all__ = ["QuoteDBPlugin"]
