"""
Tests for playlist models (PlaylistItem, MediaType, MediaParser).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timezone

from models import MediaType, MediaParser, PlaylistItem


class TestMediaType:
    """Test MediaType enum."""
    
    def test_media_type_values(self):
        """Test media type enum values."""
        assert MediaType.YOUTUBE.value == "yt"
        assert MediaType.VIMEO.value == "vi"
        assert MediaType.SOUNDCLOUD.value == "sc"
        assert MediaType.TWITCH_CLIP.value == "tc"
    
    def test_media_type_from_string(self):
        """Test creating MediaType from string."""
        assert MediaType("yt") == MediaType.YOUTUBE
        assert MediaType("vi") == MediaType.VIMEO


class TestMediaParser:
    """Test MediaParser URL parsing."""
    
    def test_parse_youtube_watch(self):
        """Test parsing YouTube watch URL."""
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.YOUTUBE
        assert media_id == "dQw4w9WgXcQ"
    
    def test_parse_youtube_short(self):
        """Test parsing YouTube short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.YOUTUBE
        assert media_id == "dQw4w9WgXcQ"
    
    def test_parse_youtube_playlist(self):
        """Test parsing YouTube playlist URL."""
        url = "https://youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.YOUTUBE_PLAYLIST
        assert media_id == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
    
    def test_parse_vimeo(self):
        """Test parsing Vimeo URL."""
        url = "https://vimeo.com/123456789"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.VIMEO
        assert media_id == "123456789"
    
    def test_parse_twitch_clip(self):
        """Test parsing Twitch clip URL."""
        url = "https://clips.twitch.tv/AwesomeClip"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.TWITCH_CLIP
        assert media_id == "AwesomeClip"
    
    def test_parse_twitch_vod(self):
        """Test parsing Twitch VOD URL."""
        url = "https://twitch.tv/videos/123456"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.TWITCH_VOD
        assert media_id == "v123456"
    
    def test_parse_soundcloud(self):
        """Test parsing SoundCloud URL."""
        url = "https://soundcloud.com/artist/track-name"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.SOUNDCLOUD
        assert media_id == url  # SoundCloud uses full URL
    
    def test_parse_dailymotion(self):
        """Test parsing Dailymotion URL."""
        url = "https://dailymotion.com/video/x123abc"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.DAILYMOTION
        assert media_id == "x123abc"
    
    def test_parse_streamable(self):
        """Test parsing Streamable URL."""
        url = "https://streamable.com/abc123"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.STREAMABLE
        assert media_id == "abc123"
    
    def test_parse_google_drive(self):
        """Test parsing Google Drive URL."""
        url = "https://drive.google.com/file/d/abc123xyz/view"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.GOOGLE_DRIVE
        assert media_id == "abc123xyz"
    
    def test_parse_raw_file_mp4(self):
        """Test parsing raw MP4 file URL."""
        url = "https://example.com/video.mp4"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.FILE
        assert media_id == url
    
    def test_parse_hls_stream(self):
        """Test parsing HLS stream URL."""
        url = "https://example.com/stream.m3u8"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.HLS
        assert media_id == url
    
    def test_parse_rtmp_stream(self):
        """Test parsing RTMP stream URL."""
        url = "rtmp://example.com/live/stream"
        media_type, media_id = MediaParser.parse(url)
        assert media_type == MediaType.RTMP
        assert media_id == url
    
    def test_parse_invalid_url(self):
        """Test parsing invalid URL raises ValueError."""
        with pytest.raises(ValueError, match="Unrecognized"):
            MediaParser.parse("https://example.com/not-a-video")
    
    def test_parse_unsupported_file_type(self):
        """Test parsing unsupported file type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported file type"):
            MediaParser.parse("https://example.com/file.txt")
    
    def test_is_valid_url_youtube(self):
        """Test is_valid_url returns True for YouTube."""
        assert MediaParser.is_valid_url("https://youtube.com/watch?v=abc")
    
    def test_is_valid_url_invalid(self):
        """Test is_valid_url returns False for invalid URL."""
        assert not MediaParser.is_valid_url("https://example.com/nope")


class TestPlaylistItem:
    """Test PlaylistItem model."""
    
    def test_create_item(self):
        """Test creating a playlist item."""
        item = PlaylistItem(
            id="abc123",
            media_type=MediaType.YOUTUBE,
            media_id="dQw4w9WgXcQ",
            title="Never Gonna Give You Up",
            duration=213,
            added_by="user1",
        )
        assert item.id == "abc123"
        assert item.media_type == MediaType.YOUTUBE
        assert item.media_id == "dQw4w9WgXcQ"
        assert item.title == "Never Gonna Give You Up"
        assert item.duration == 213
        assert item.added_by == "user1"
    
    def test_item_url_youtube(self):
        """Test URL reconstruction for YouTube."""
        item = PlaylistItem(
            id="abc",
            media_type=MediaType.YOUTUBE,
            media_id="dQw4w9WgXcQ",
            title="Test",
            duration=0,
            added_by="user",
        )
        assert item.url == "https://youtube.com/watch?v=dQw4w9WgXcQ"
    
    def test_item_url_vimeo(self):
        """Test URL reconstruction for Vimeo."""
        item = PlaylistItem(
            id="abc",
            media_type=MediaType.VIMEO,
            media_id="123456",
            title="Test",
            duration=0,
            added_by="user",
        )
        assert item.url == "https://vimeo.com/123456"
    
    def test_formatted_duration_unknown(self):
        """Test formatted duration for unknown duration."""
        item = PlaylistItem(
            id="abc",
            media_type=MediaType.YOUTUBE,
            media_id="test",
            title="Test",
            duration=0,
            added_by="user",
        )
        assert item.formatted_duration == "??:??"
    
    def test_formatted_duration_minutes(self):
        """Test formatted duration for minutes."""
        item = PlaylistItem(
            id="abc",
            media_type=MediaType.YOUTUBE,
            media_id="test",
            title="Test",
            duration=213,  # 3:33
            added_by="user",
        )
        assert item.formatted_duration == "3:33"
    
    def test_formatted_duration_hours(self):
        """Test formatted duration for hours."""
        item = PlaylistItem(
            id="abc",
            media_type=MediaType.YOUTUBE,
            media_id="test",
            title="Test",
            duration=3665,  # 1:01:05
            added_by="user",
        )
        assert item.formatted_duration == "1:01:05"
    
    def test_to_dict(self):
        """Test serialization to dict."""
        item = PlaylistItem(
            id="abc123",
            media_type=MediaType.YOUTUBE,
            media_id="test",
            title="Test Video",
            duration=100,
            added_by="user1",
            thumbnail_url="https://example.com/thumb.jpg",
        )
        data = item.to_dict()
        
        assert data["id"] == "abc123"
        assert data["media_type"] == "yt"
        assert data["media_id"] == "test"
        assert data["title"] == "Test Video"
        assert data["duration"] == 100
        assert data["added_by"] == "user1"
        assert data["thumbnail_url"] == "https://example.com/thumb.jpg"
        assert "added_at" in data
        assert "url" in data
    
    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "id": "abc123",
            "media_type": "yt",
            "media_id": "test",
            "title": "Test Video",
            "duration": 100,
            "added_by": "user1",
            "added_at": "2025-11-24T12:00:00+00:00",
            "thumbnail_url": "https://example.com/thumb.jpg",
            "temp": False,
        }
        item = PlaylistItem.from_dict(data)
        
        assert item.id == "abc123"
        assert item.media_type == MediaType.YOUTUBE
        assert item.media_id == "test"
        assert item.title == "Test Video"
        assert item.duration == 100
        assert item.added_by == "user1"
        assert item.thumbnail_url == "https://example.com/thumb.jpg"
        assert not item.temp
    
    def test_roundtrip_serialization(self):
        """Test that serialization round-trips correctly."""
        original = PlaylistItem(
            id="abc123",
            media_type=MediaType.VIMEO,
            media_id="999",
            title="Test",
            duration=150,
            added_by="user2",
        )
        data = original.to_dict()
        restored = PlaylistItem.from_dict(data)
        
        assert restored.id == original.id
        assert restored.media_type == original.media_type
        assert restored.media_id == original.media_id
        assert restored.title == original.title
        assert restored.duration == original.duration
        assert restored.added_by == original.added_by
