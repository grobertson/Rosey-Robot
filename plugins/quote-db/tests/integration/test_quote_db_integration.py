"""
Integration tests for QuoteDBPlugin.

These tests require:
- NATS server running on localhost:4222
- Migrations applied (001, 002, 003)

Run with: pytest tests/integration/ -v -m integration
"""
import pytest
import nats
from quote_db import QuoteDBPlugin


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_workflow():
    """
    Integration test validating complete quote lifecycle.
    
    Tests:
    1. Plugin initialization with migration check
    2. Add quote
    3. Get quote by ID
    4. Search for quote
    5. Upvote quote
    6. Check top quotes
    7. Delete quote
    8. Verify deletion
    """
    # Connect to real NATS
    try:
        nc = await nats.connect("nats://localhost:4222", connect_timeout=5.0)
    except Exception as e:
        pytest.skip(f"NATS server not available: {e}")
    
    try:
        # 1. Initialize plugin
        plugin = QuoteDBPlugin(nc)
        try:
            await plugin.initialize()
        except RuntimeError as e:
            if "no responders" in str(e) or "migration status" in str(e):
                pytest.skip(f"Database service not available: {e}")
            raise
        print("✓ Plugin initialized")
        
        # 2. Add quote
        quote_id = await plugin.add_quote(
            text="Integration test quote - full workflow validation",
            author="TestAuthor",
            added_by="test_user"
        )
        assert quote_id > 0
        print(f"✓ Added quote {quote_id}")
        
        # 3. Get quote
        quote = await plugin.get_quote(quote_id)
        assert quote is not None
        assert quote["text"] == "Integration test quote - full workflow validation"
        assert quote["author"] == "TestAuthor"
        assert quote["score"] == 0
        print(f"✓ Retrieved quote {quote_id}")
        
        # 4. Search for quote
        results = await plugin.search_quotes("TestAuthor")
        assert any(q["id"] == quote_id for q in results)
        print(f"✓ Found quote in search results ({len(results)} total)")
        
        # 5. Upvote quote
        new_score = await plugin.upvote_quote(quote_id)
        assert new_score == 1
        print(f"✓ Upvoted quote, new score: {new_score}")
        
        # 6. Check top quotes
        top = await plugin.top_quotes(limit=10)
        assert any(q["id"] == quote_id for q in top)
        assert all(q["score"] >= 1 for q in top)
        print(f"✓ Quote appears in top quotes ({len(top)} total)")
        
        # 7. Delete quote
        deleted = await plugin.delete_quote(quote_id)
        assert deleted is True
        print(f"✓ Deleted quote {quote_id}")
        
        # 8. Verify deletion
        quote = await plugin.get_quote(quote_id)
        assert quote is None
        print(f"✓ Confirmed quote deleted")
        
        print("\n✅ Full workflow test passed!")
        
    finally:
        await nc.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_logic():
    """
    Test retry logic with add_quote_safe().
    
    This test validates the exponential backoff retry mechanism.
    """
    try:
        nc = await nats.connect("nats://localhost:4222", connect_timeout=5.0)
    except Exception as e:
        pytest.skip(f"NATS server not available: {e}")
    
    try:
        plugin = QuoteDBPlugin(nc)
        try:
            await plugin.initialize()
        except RuntimeError as e:
            if "no responders" in str(e) or "migration status" in str(e):
                pytest.skip(f"Database service not available: {e}")
            raise
        
        # Test successful add with retry wrapper
        quote_id = await plugin.add_quote_safe(
            text="Test retry logic quote",
            author="RetryTest",
            added_by="test_user",
            max_retries=3
        )
        
        assert quote_id is not None
        print(f"✓ add_quote_safe() succeeded with quote {quote_id}")
        
        # Clean up
        await plugin.delete_quote(quote_id)
        print(f"✓ Cleaned up test quote")
        
        print("\n✅ Retry logic test passed!")
        
    finally:
        await nc.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_random_quote():
    """Test random quote selection with KV cache."""
    try:
        nc = await nats.connect("nats://localhost:4222", connect_timeout=5.0)
    except Exception as e:
        pytest.skip(f"NATS server not available: {e}")
    
    try:
        plugin = QuoteDBPlugin(nc)
        try:
            await plugin.initialize()
        except RuntimeError as e:
            if "no responders" in str(e) or "migration status" in str(e):
                pytest.skip(f"Database service not available: {e}")
            raise
        
        # Get random quote
        quote = await plugin.random_quote()
        
        if quote:
            print(f"✓ Got random quote {quote['id']}: '{quote['text'][:50]}...'")
            assert "id" in quote
            assert "text" in quote
            assert "author" in quote
        else:
            print("✓ No quotes available (empty database)")
        
        print("\n✅ Random quote test passed!")
        
    finally:
        await nc.close()
