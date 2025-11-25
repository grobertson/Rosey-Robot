"""
Metadata fetching for playlist items.

Fetches titles, durations, thumbnails from media platforms via oEmbed APIs.
"""

import httpx
from typing import Optional, Dict, Any
import os
import logging

try:
    from .models import MediaType
except ImportError:
    from models import MediaType

logger = logging.getLogger(__name__)


class MetadataFetcher:
    """
    Fetch metadata for media items.
    
    Supports:
    - YouTube (via oEmbed)
    - Vimeo (via oEmbed)
    - SoundCloud (via oEmbed)
    
    Uses oEmbed APIs for simplicity and no API key requirements.
    For production with high volume, consider proper APIs with keys.
    """
    
    OEMBED_URLS = {
        MediaType.YOUTUBE: "https://www.youtube.com/oembed",
        MediaType.VIMEO: "https://vimeo.com/api/oembed.json",
        MediaType.SOUNDCLOUD: "https://soundcloud.com/oembed",
    }
    
    def __init__(self, youtube_api_key: Optional[str] = None, timeout: float = 10.0):
        """
        Initialize metadata fetcher.
        
        Args:
            youtube_api_key: Optional YouTube Data API key for enhanced metadata
            timeout: Request timeout in seconds
        """
        self._youtube_api_key = youtube_api_key or os.getenv("YOUTUBE_API_KEY")
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client
    
    async def fetch(self, media_type: MediaType, media_id: str) -> Dict[str, Any]:
        """
        Fetch metadata for a media item.
        
        Args:
            media_type: Type of media (YOUTUBE, VIMEO, etc.)
            media_id: Media identifier (video ID, track path, etc.)
        
        Returns:
            Dict with keys:
            - title (str): Media title
            - duration (int): Duration in seconds (0 if unavailable)
            - thumbnail (Optional[str]): Thumbnail URL
            - channel (Optional[str]): Channel/author name
        """
        try:
            if media_type == MediaType.YOUTUBE:
                return await self._fetch_youtube(media_id)
            elif media_type == MediaType.VIMEO:
                return await self._fetch_vimeo(media_id)
            elif media_type == MediaType.SOUNDCLOUD:
                return await self._fetch_soundcloud(media_id)
            else:
                # Unsupported type - return basic info
                return {
                    "title": media_id,
                    "duration": 0,
                    "thumbnail": None,
                    "channel": None,
                }
        except Exception as e:
            logger.error(f"Failed to fetch metadata for {media_type.value}:{media_id}: {e}")
            return {
                "title": f"{media_type.value}:{media_id}",
                "duration": 0,
                "thumbnail": None,
                "channel": None,
            }
    
    async def _fetch_youtube(self, video_id: str) -> Dict[str, Any]:
        """
        Fetch YouTube metadata via oEmbed.
        
        Args:
            video_id: YouTube video ID
        
        Returns:
            Metadata dict
        """
        client = await self._get_client()
        
        # Construct oEmbed URL
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        oembed_url = f"{self.OEMBED_URLS[MediaType.YOUTUBE]}?url={video_url}&format=json"
        
        try:
            response = await client.get(oembed_url)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "title": data.get("title", video_id),
                    "duration": 0,  # oEmbed doesn't provide duration
                    "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                    "channel": data.get("author_name"),
                }
            else:
                logger.warning(f"YouTube oEmbed failed with status {response.status_code}")
        except Exception as e:
            logger.error(f"YouTube oEmbed request failed: {e}")
        
        # Fallback
        return {
            "title": f"YouTube: {video_id}",
            "duration": 0,
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            "channel": None,
        }
    
    async def _fetch_vimeo(self, video_id: str) -> Dict[str, Any]:
        """
        Fetch Vimeo metadata via oEmbed.
        
        Args:
            video_id: Vimeo video ID
        
        Returns:
            Metadata dict
        """
        client = await self._get_client()
        
        # Construct oEmbed URL
        video_url = f"https://vimeo.com/{video_id}"
        oembed_url = f"{self.OEMBED_URLS[MediaType.VIMEO]}?url={video_url}"
        
        try:
            response = await client.get(oembed_url)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "title": data.get("title", video_id),
                    "duration": data.get("duration", 0),
                    "thumbnail": data.get("thumbnail_url"),
                    "channel": data.get("author_name"),
                }
            else:
                logger.warning(f"Vimeo oEmbed failed with status {response.status_code}")
        except Exception as e:
            logger.error(f"Vimeo oEmbed request failed: {e}")
        
        # Fallback
        return {
            "title": f"Vimeo: {video_id}",
            "duration": 0,
            "thumbnail": None,
            "channel": None,
        }
    
    async def _fetch_soundcloud(self, track_path: str) -> Dict[str, Any]:
        """
        Fetch SoundCloud metadata via oEmbed.
        
        Args:
            track_path: Full SoundCloud URL (stored as media_id for SoundCloud)
        
        Returns:
            Metadata dict
        """
        client = await self._get_client()
        
        # SoundCloud media_id is the full URL
        oembed_url = f"{self.OEMBED_URLS[MediaType.SOUNDCLOUD]}?url={track_path}&format=json"
        
        try:
            response = await client.get(oembed_url)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "title": data.get("title", track_path),
                    "duration": 0,  # oEmbed doesn't provide duration
                    "thumbnail": data.get("thumbnail_url"),
                    "channel": data.get("author_name"),
                }
            else:
                logger.warning(f"SoundCloud oEmbed failed with status {response.status_code}")
        except Exception as e:
            logger.error(f"SoundCloud oEmbed request failed: {e}")
        
        # Fallback
        return {
            "title": f"SoundCloud: {track_path}",
            "duration": 0,
            "thumbnail": None,
            "channel": None,
        }
    
    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
