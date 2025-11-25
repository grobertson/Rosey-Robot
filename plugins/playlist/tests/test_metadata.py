"""
Tests for metadata fetcher.
"""

import pytest
from unittest.mock import AsyncMock, patch
import httpx
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from metadata import MetadataFetcher
from models import MediaType


@pytest.mark.asyncio
class TestMetadataFetcher:
    """Tests for MetadataFetcher class."""
    
    async def test_fetch_youtube_success(self):
        """Test fetching YouTube metadata via oEmbed."""
        fetcher = MetadataFetcher()
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "Test Video",
            "author_name": "Test Channel",
        }
        
        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            metadata = await fetcher.fetch(MediaType.YOUTUBE, "dQw4w9WgXcQ")
        
        assert metadata["title"] == "Test Video"
        assert metadata["channel"] == "Test Channel"
        assert "youtube.com" in metadata["thumbnail"]
        await fetcher.close()
    
    async def test_fetch_youtube_fallback(self):
        """Test YouTube fallback when oEmbed fails."""
        fetcher = MetadataFetcher()
        
        # Mock HTTP error
        mock_response = AsyncMock()
        mock_response.status_code = 404
        
        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            metadata = await fetcher.fetch(MediaType.YOUTUBE, "dQw4w9WgXcQ")
        
        assert "YouTube" in metadata["title"]
        assert "youtube.com" in metadata["thumbnail"]
        await fetcher.close()
    
    async def test_fetch_vimeo_success(self):
        """Test fetching Vimeo metadata."""
        fetcher = MetadataFetcher()
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "Vimeo Test",
            "author_name": "Vimeo User",
            "duration": 120,
            "thumbnail_url": "https://i.vimeocdn.com/...",
        }
        
        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            metadata = await fetcher.fetch(MediaType.VIMEO, "123456")
        
        assert metadata["title"] == "Vimeo Test"
        assert metadata["channel"] == "Vimeo User"
        assert metadata["duration"] == 120
        assert metadata["thumbnail"] == "https://i.vimeocdn.com/..."
        await fetcher.close()
    
    async def test_fetch_soundcloud_success(self):
        """Test fetching SoundCloud metadata."""
        fetcher = MetadataFetcher()
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "Cool Track",
            "author_name": "Artist Name",
            "thumbnail_url": "https://i1.sndcdn.com/...",
        }
        
        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            metadata = await fetcher.fetch(
                MediaType.SOUNDCLOUD,
                "https://soundcloud.com/artist/track"
            )
        
        assert metadata["title"] == "Cool Track"
        assert metadata["channel"] == "Artist Name"
        await fetcher.close()
    
    async def test_fetch_unsupported_type(self):
        """Test fetching metadata for unsupported type."""
        fetcher = MetadataFetcher()
        
        metadata = await fetcher.fetch(MediaType.DAILYMOTION, "abc123")
        
        assert metadata["title"] == "abc123"
        assert metadata["duration"] == 0
        await fetcher.close()
    
    async def test_fetch_exception_handling(self):
        """Test exception handling during fetch."""
        fetcher = MetadataFetcher()
        
        # Mock exception
        with patch.object(httpx.AsyncClient, "get", side_effect=Exception("Network error")):
            metadata = await fetcher.fetch(MediaType.YOUTUBE, "dQw4w9WgXcQ")
        
        # Should return fallback data
        assert "yt:" in metadata["title"]
        await fetcher.close()
    
    async def test_client_reuse(self):
        """Test that HTTP client is reused."""
        fetcher = MetadataFetcher()
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"title": "Test"}
        
        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            await fetcher.fetch(MediaType.YOUTUBE, "vid1")
            await fetcher.fetch(MediaType.YOUTUBE, "vid2")
        
        # Client should be created once and reused
        assert fetcher._client is not None
        await fetcher.close()
        assert fetcher._client is None
