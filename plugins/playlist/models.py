"""
Playlist Models

Data models for playlist items and media parsing.
Migrated and enhanced from lib/playlist.py and lib/media_link.py.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from urllib.parse import parse_qsl, urlparse


class MediaType(Enum):
    """Supported media types (platforms)."""
    YOUTUBE = "yt"
    YOUTUBE_PLAYLIST = "yp"
    VIMEO = "vi"
    DAILYMOTION = "dm"
    SOUNDCLOUD = "sc"
    TWITCH_CLIP = "tc"
    TWITCH_VOD = "tv"
    TWITCH_STREAM = "tw"
    STREAMABLE = "sb"
    GOOGLE_DRIVE = "gd"
    IMGUR = "im"
    CUSTOM_EMBED = "cu"
    FILE = "fi"
    RTMP = "rt"
    HLS = "hl"
    UNKNOWN = "unknown"


@dataclass
class PlaylistItem:
    """
    Represents an item in the playlist.
    
    This is a modernized version of the CyTube PlaylistItem
    with better typing and serialization support.
    
    Attributes:
        id: Unique ID within playlist (generated if not provided)
        media_type: Platform/type of media
        media_id: Platform-specific identifier
        title: Human-readable title
        duration: Duration in seconds (0 if unknown)
        added_by: Username who queued this item
        added_at: Timestamp when added
        thumbnail_url: Optional thumbnail/preview image
        channel_name: Optional channel/uploader name
        temp: Whether item is temporary (removed after playing)
    """
    id: str
    media_type: MediaType
    media_id: str
    title: str
    duration: int
    added_by: str
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    thumbnail_url: Optional[str] = None
    channel_name: Optional[str] = None
    temp: bool = False
    
    @property
    def url(self) -> str:
        """Reconstruct URL from media type and ID."""
        url_patterns = {
            MediaType.YOUTUBE: f"https://youtube.com/watch?v={self.media_id}",
            MediaType.YOUTUBE_PLAYLIST: f"https://youtube.com/playlist?list={self.media_id}",
            MediaType.VIMEO: f"https://vimeo.com/{self.media_id}",
            MediaType.DAILYMOTION: f"https://dailymotion.com/video/{self.media_id}",
            MediaType.SOUNDCLOUD: f"https://soundcloud.com/{self.media_id}",
            MediaType.TWITCH_CLIP: f"https://clips.twitch.tv/{self.media_id}",
            MediaType.TWITCH_VOD: f"https://twitch.tv/videos/{self.media_id}",
            MediaType.TWITCH_STREAM: f"https://twitch.tv/{self.media_id}",
            MediaType.STREAMABLE: f"https://streamable.com/{self.media_id}",
            MediaType.GOOGLE_DRIVE: f"https://drive.google.com/file/d/{self.media_id}",
            MediaType.IMGUR: f"https://imgur.com/a/{self.media_id}",
        }
        return url_patterns.get(self.media_type, self.media_id)
    
    @property
    def formatted_duration(self) -> str:
        """Format duration as HH:MM:SS or MM:SS."""
        if self.duration == 0:
            return "??:??"
        hours, remainder = divmod(self.duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    
    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict for NATS messages."""
        return {
            "id": self.id,
            "media_type": self.media_type.value,
            "media_id": self.media_id,
            "title": self.title,
            "duration": self.duration,
            "added_by": self.added_by,
            "added_at": self.added_at.isoformat(),
            "url": self.url,
            "formatted_duration": self.formatted_duration,
            "thumbnail_url": self.thumbnail_url,
            "channel_name": self.channel_name,
            "temp": self.temp,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PlaylistItem':
        """Deserialize from JSON-compatible dict."""
        return cls(
            id=data["id"],
            media_type=MediaType(data["media_type"]),
            media_id=data["media_id"],
            title=data["title"],
            duration=data["duration"],
            added_by=data["added_by"],
            added_at=datetime.fromisoformat(data["added_at"]),
            thumbnail_url=data.get("thumbnail_url"),
            channel_name=data.get("channel_name"),
            temp=data.get("temp", False),
        )


class MediaParser:
    """
    Parse URLs to extract media type and ID.
    
    Migrated from lib/media_link.py with modernized patterns.
    """
    
    # URL patterns: (regex, media_type, id_extraction_format)
    # Based on CyTube's media link parsing
    PATTERNS = [
        (r'youtube\.com/watch\?([^#]+)', MediaType.YOUTUBE, '{v}'),
        (r'youtu\.be/([^\?&#]+)', MediaType.YOUTUBE, '{0}'),
        (r'youtube\.com/playlist\?([^#]+)', MediaType.YOUTUBE_PLAYLIST, '{list}'),
        (r'clips\.twitch\.tv/([A-Za-z]+)', MediaType.TWITCH_CLIP, '{0}'),
        (r'twitch\.tv/videos/(\d+)', MediaType.TWITCH_VOD, 'v{0}'),
        (r'twitch\.tv/([\w-]+)', MediaType.TWITCH_STREAM, '{0}'),
        (r'vimeo\.com/([^\?&#]+)', MediaType.VIMEO, '{0}'),
        (r'dailymotion\.com/video/([^\?&#_]+)', MediaType.DAILYMOTION, '{0}'),
        (r'soundcloud\.com/([^\?&#]+)', MediaType.SOUNDCLOUD, '{url}'),
        (r'(?:docs|drive)\.google\.com/file/d/([a-zA-Z0-9_-]+)', MediaType.GOOGLE_DRIVE, '{0}'),
        (r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)', MediaType.GOOGLE_DRIVE, '{0}'),
        (r'imgur\.com/a/([^\?&#]+)', MediaType.IMGUR, '{0}'),
        (r'streamable\.com/([\w-]+)', MediaType.STREAMABLE, '{0}'),
        (r'(.*\.m3u8)', MediaType.HLS, '{url}'),
    ]
    
    FILE_TYPES = ['.mp4', '.flv', '.webm', '.ogg', '.ogv', '.mp3', '.mov', '.m4a']
    
    @classmethod
    def parse(cls, url: str) -> tuple[MediaType, str]:
        """
        Parse a URL to extract media type and ID.
        
        Args:
            url: Media URL to parse
            
        Returns:
            Tuple of (MediaType, media_id)
            
        Raises:
            ValueError: If URL format not recognized or not supported
        """
        url = url.strip().replace('feature=player_embedded&', '')
        parsed_url = urlparse(url)
        
        # RTMP streams
        if parsed_url.scheme == 'rtmp':
            return MediaType.RTMP, url
        
        # Try each pattern
        for pattern, media_type, id_format in cls.PATTERNS:
            match = re.search(pattern, url)
            if match:
                args = match.groups()
                kwargs = dict(parse_qsl(parsed_url.query))
                kwargs['url'] = url
                
                # Extract ID using format string
                try:
                    media_id = id_format.format(*args, **kwargs)
                    return media_type, media_id
                except (KeyError, IndexError):
                    continue
        
        # HTTPS files
        if parsed_url.scheme == 'https':
            _, ext = parsed_url.path.rsplit('.', 1) if '.' in parsed_url.path else ('', '')
            ext = f'.{ext}' if ext else ''
            
            if ext in cls.FILE_TYPES:
                return MediaType.FILE, url
            
            if ext == '.json':
                return MediaType.CUSTOM_EMBED, url
            
            if ext:
                raise ValueError(
                    f'Unsupported file type: {ext}. '
                    f'Supported: {", ".join(cls.FILE_TYPES)}'
                )
        
        raise ValueError(f'Unrecognized or unsupported media URL: {url}')
    
    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """Check if URL is a supported media URL."""
        try:
            cls.parse(url)
            return True
        except ValueError:
            return False
