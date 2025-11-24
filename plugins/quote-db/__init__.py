"""Quote database plugin package."""
import sys

try:
    from .quote_db import QuoteDBPlugin
except ImportError:
    # For standalone test runs when package context is not available
    # Check if we're being imported as a module (no parent package)
    if __package__ is None or __package__ == '':
        try:
            from quote_db import QuoteDBPlugin
        except ImportError as e:
            # If this also fails, re-raise with helpful message
            raise ImportError(
                f"Cannot import QuoteDBPlugin. Ensure quote_db.py is in the "
                f"Python path or use package import. Original error: {e}"
            ) from e
    else:
        # Re-raise if it's a package import failure (likely missing dependency)
        raise

__version__ = "1.0.0"
__all__ = ["QuoteDBPlugin"]
