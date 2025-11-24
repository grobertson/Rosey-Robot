"""Quote database plugin package."""
try:
    from .quote_db import QuoteDBPlugin
except ImportError as e:
    # For standalone test runs when package context is not available
    if "attempted relative import" in str(e):
        from quote_db import QuoteDBPlugin
    else:
        # Re-raise if it's a different import error (e.g., missing dependency)
        raise

__version__ = "1.0.0"
__all__ = ["QuoteDBPlugin"]
