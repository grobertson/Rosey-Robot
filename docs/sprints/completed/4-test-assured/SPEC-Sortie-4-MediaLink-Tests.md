# SPEC-Commit-4: lib/media_link.py Tests

## Objective
Create comprehensive unit tests for `lib/media_link.py`, covering URL parsing and conversion for various media providers (YouTube, Twitch, Vimeo, etc.), media link construction, and validation. This module is critical for handling user-submitted media URLs in the bot.

## Target Coverage
- **Overall**: 95%
- **MediaLink.__init__**: 100%
- **MediaLink.url property**: 100%
- **MediaLink.from_url classmethod**: 95%
- **URL pattern matching**: 100%

## Module Analysis

**File**: `lib/media_link.py`

**Key Components**:
1. **MediaLink Class**
   - Complexity: Medium (extensive URL pattern matching)
   - Attributes: `type` (e.g., 'yt', 'tw'), `id` (media identifier)
   - String representations: `__str__` ("type:id"), `__repr__`, `__eq__`
   - Property: `url` - converts type:id back to full URL

2. **URL Parsing (from_url classmethod)**
   - Complexity: High (24 URL patterns, special cases)
   - Supported providers:
     * YouTube (videos: yt, playlists: yp)
     * Twitch (clips: tc, videos: tv, channels: tw)
     * Vimeo (vi), Dailymotion (dm), Imgur albums (im)
     * SoundCloud (sc), Google Drive (gd), Vid.me (vm)
     * Livestream (li), Ustream (us), Hitbox/Smashcast (hb)
     * Streamable (sb), M3U8 streams (hl)
     * Raw files (fi), Custom embeds (cm), RTMP streams (rt)
   - Special handling: RTMP scheme, HTTPS file extensions, custom types (dm:, fi:, cm:, generic XX:)
   - Validation: Requires HTTPS for raw files, validates file extensions

3. **URL Format Templates**
   - LINK_TO_URL: Dict mapping type codes to URL templates
   - URL_TO_LINK: List of (regex, type_format, id_format) tuples
   - FILE_TYPES: Supported raw file extensions (.mp4, .flv, .webm, etc.)

**Dependencies**:
- Standard library: `os`, `re`, `logging`, `urllib.parse`

**Edge Cases**:
- Unknown media types (logging warning, fallback to "type:id")
- Invalid URLs (ValueError)
- HTTP vs HTTPS (HTTP rejected for raw files)
- Query string parsing (YouTube playlist IDs, feature flags)
- Special URL formats (shortened youtube.com/youtu.be, embedded vid.me)
- Custom type prefixes (dm:, fi:, cm:, generic XX:)

## Test File Structure

**File**: `tests/unit/test_media_link.py`

**Test Classes**:
1. `TestMediaLinkInit` - Constructor and basic properties
2. `TestMediaLinkStringRepresentation` - __str__, __repr__, __eq__
3. `TestMediaLinkUrl` - URL property and unknown types
4. `TestFromUrlYoutube` - YouTube video and playlist parsing
5. `TestFromUrlTwitch` - Twitch clips, videos, channels
6. `TestFromUrlOtherProviders` - Vimeo, Dailymotion, SoundCloud, etc.
7. `TestFromUrlRawFiles` - HTTPS files, extensions, validation
8. `TestFromUrlCustomTypes` - dm:, fi:, cm:, generic XX: prefixes
9. `TestFromUrlEdgeCases` - RTMP, errors, malformed URLs

## Implementation

### tests/unit/test_media_link.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest
from unittest.mock import patch
from lib.media_link import MediaLink


class TestMediaLinkInit:
    """Test MediaLink initialization"""

    def test_init_basic(self):
        """Create MediaLink with type and ID"""
        link = MediaLink('yt', 'dQw4w9WgXcQ')
        assert link.type == 'yt'
        assert link.id == 'dQw4w9WgXcQ'

    def test_init_different_types(self):
        """Create MediaLink with various types"""
        link_yt = MediaLink('yt', 'video123')
        link_tw = MediaLink('tw', 'channel_name')
        link_dm = MediaLink('dm', 'dailymotion_id')

        assert link_yt.type == 'yt'
        assert link_tw.type == 'tw'
        assert link_dm.type == 'dm'

    def test_init_empty_id(self):
        """Create MediaLink with empty ID"""
        link = MediaLink('yt', '')
        assert link.type == 'yt'
        assert link.id == ''

    def test_init_special_characters_in_id(self):
        """Create MediaLink with special characters in ID"""
        link = MediaLink('sc', 'artist/song-name_123')
        assert link.id == 'artist/song-name_123'


class TestMediaLinkStringRepresentation:
    """Test MediaLink string representations and equality"""

    def test_str(self):
        """Test __str__ returns 'type:id' format"""
        link = MediaLink('yt', 'dQw4w9WgXcQ')
        assert str(link) == 'yt:dQw4w9WgXcQ'

    def test_str_different_types(self):
        """Test __str__ with various types"""
        assert str(MediaLink('tw', 'ninja')) == 'tw:ninja'
        assert str(MediaLink('dm', 'x123abc')) == 'dm:x123abc'

    def test_repr(self):
        """Test __repr__ returns constructor format"""
        link = MediaLink('vi', '123456')
        assert repr(link) == "MediaLink('vi', '123456')"

    def test_eq_same_link(self):
        """Test equality for identical links"""
        link1 = MediaLink('yt', 'video123')
        link2 = MediaLink('yt', 'video123')
        assert link1 == link2

    def test_eq_different_id(self):
        """Test inequality for different IDs"""
        link1 = MediaLink('yt', 'video123')
        link2 = MediaLink('yt', 'video456')
        assert link1 != link2

    def test_eq_different_type(self):
        """Test inequality for different types"""
        link1 = MediaLink('yt', 'video123')
        link2 = MediaLink('tw', 'video123')
        assert link1 != link2

    def test_eq_different_class(self):
        """Test inequality with non-MediaLink object"""
        link = MediaLink('yt', 'video123')
        assert link != "yt:video123"
        assert link != {'type': 'yt', 'id': 'video123'}


class TestMediaLinkUrl:
    """Test MediaLink.url property"""

    def test_url_youtube(self):
        """Get URL for YouTube video"""
        link = MediaLink('yt', 'dQw4w9WgXcQ')
        assert link.url == 'https://youtube.com/watch?v=dQw4w9WgXcQ'

    def test_url_youtube_playlist(self):
        """Get URL for YouTube playlist"""
        link = MediaLink('yp', 'PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf')
        assert link.url == 'https://youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf'

    def test_url_twitch_channel(self):
        """Get URL for Twitch channel"""
        link = MediaLink('tw', 'ninja')
        assert link.url == 'https://twitch.tv/ninja'

    def test_url_vimeo(self):
        """Get URL for Vimeo video"""
        link = MediaLink('vi', '123456789')
        assert link.url == 'https://vimeo.com/123456789'

    def test_url_dailymotion(self):
        """Get URL for Dailymotion video"""
        link = MediaLink('dm', 'x7tgad0')
        assert link.url == 'https://dailymotion.com/video/x7tgad0'

    def test_url_soundcloud(self):
        """Get URL for SoundCloud track"""
        link = MediaLink('sc', 'artist/track-name')
        assert link.url == 'https://soundcloud.com/artist/track-name'

    def test_url_raw_file(self):
        """Get URL for raw file (fi type)"""
        link = MediaLink('fi', 'https://example.com/video.mp4')
        assert link.url == 'https://example.com/video.mp4'

    def test_url_m3u8_stream(self):
        """Get URL for M3U8 stream (hl type)"""
        link = MediaLink('hl', 'https://example.com/stream.m3u8')
        assert link.url == 'https://example.com/stream.m3u8'

    def test_url_rtmp_stream(self):
        """Get URL for RTMP stream (rt type)"""
        link = MediaLink('rt', 'rtmp://example.com/live/stream')
        assert link.url == 'rtmp://example.com/live/stream'

    @patch('lib.media_link.MediaLink.logger')
    def test_url_unknown_type(self, mock_logger):
        """Get URL for unknown type logs warning and returns fallback"""
        link = MediaLink('unknown', 'test123')
        url = link.url
        assert url == 'unknown:test123'
        mock_logger.warning.assert_called_once()


class TestFromUrlYoutube:
    """Test MediaLink.from_url for YouTube URLs"""

    def test_from_url_youtube_watch(self):
        """Parse standard YouTube watch URL"""
        url = 'https://youtube.com/watch?v=dQw4w9WgXcQ'
        link = MediaLink.from_url(url)
        assert link.type == 'yt'
        assert link.id == 'dQw4w9WgXcQ'

    def test_from_url_youtube_short(self):
        """Parse shortened youtu.be URL"""
        url = 'https://youtu.be/dQw4w9WgXcQ'
        link = MediaLink.from_url(url)
        assert link.type == 'yt'
        assert link.id == 'dQw4w9WgXcQ'

    def test_from_url_youtube_with_timestamp(self):
        """Parse YouTube URL with timestamp parameter"""
        url = 'https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s'
        link = MediaLink.from_url(url)
        assert link.type == 'yt'
        assert link.id == 'dQw4w9WgXcQ'

    def test_from_url_youtube_embedded_feature_removed(self):
        """Parse YouTube URL with feature=player_embedded (should be removed)"""
        url = 'https://youtube.com/watch?feature=player_embedded&v=dQw4w9WgXcQ'
        link = MediaLink.from_url(url)
        assert link.type == 'yt'
        assert link.id == 'dQw4w9WgXcQ'

    def test_from_url_youtube_playlist(self):
        """Parse YouTube playlist URL"""
        url = 'https://youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf'
        link = MediaLink.from_url(url)
        assert link.type == 'yp'
        assert link.id == 'PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf'

    def test_from_url_youtube_short_with_query(self):
        """Parse youtu.be URL with query parameters"""
        url = 'https://youtu.be/dQw4w9WgXcQ?si=abc123'
        link = MediaLink.from_url(url)
        assert link.type == 'yt'
        assert link.id == 'dQw4w9WgXcQ'


class TestFromUrlTwitch:
    """Test MediaLink.from_url for Twitch URLs"""

    def test_from_url_twitch_clip(self):
        """Parse Twitch clip URL"""
        url = 'https://clips.twitch.tv/AwesomeClipSlug'
        link = MediaLink.from_url(url)
        assert link.type == 'tc'
        assert link.id == 'AwesomeClipSlug'

    def test_from_url_twitch_video(self):
        """Parse Twitch video URL"""
        url = 'https://twitch.tv/videos/123456789'
        link = MediaLink.from_url(url)
        assert link.type == 'tv'
        assert link.id == 'v123456789'

    def test_from_url_twitch_channel(self):
        """Parse Twitch channel URL"""
        url = 'https://twitch.tv/ninja'
        link = MediaLink.from_url(url)
        assert link.type == 'tw'
        assert link.id == 'ninja'

    def test_from_url_twitch_video_legacy(self):
        """Parse legacy Twitch video URL (/username/v/12345)"""
        url = 'https://twitch.tv/username/v/12345'
        link = MediaLink.from_url(url)
        assert link.type == 'tv'
        assert link.id == 'v12345'

    def test_from_url_twitch_channel_with_hyphen(self):
        """Parse Twitch channel with hyphen/underscore"""
        url = 'https://twitch.tv/channel-name_123'
        link = MediaLink.from_url(url)
        assert link.type == 'tw'
        assert link.id == 'channel-name_123'


class TestFromUrlOtherProviders:
    """Test MediaLink.from_url for various other providers"""

    def test_from_url_vimeo(self):
        """Parse Vimeo URL"""
        url = 'https://vimeo.com/123456789'
        link = MediaLink.from_url(url)
        assert link.type == 'vi'
        assert link.id == '123456789'

    def test_from_url_dailymotion(self):
        """Parse Dailymotion URL"""
        url = 'https://dailymotion.com/video/x7tgad0'
        link = MediaLink.from_url(url)
        assert link.type == 'dm'
        assert link.id == 'x7tgad0'

    def test_from_url_dailymotion_with_suffix(self):
        """Parse Dailymotion URL ignoring suffix after _"""
        url = 'https://dailymotion.com/video/x7tgad0_video-title'
        link = MediaLink.from_url(url)
        assert link.type == 'dm'
        assert link.id == 'x7tgad0'

    def test_from_url_soundcloud(self):
        """Parse SoundCloud URL"""
        url = 'https://soundcloud.com/artist/track-name'
        link = MediaLink.from_url(url)
        assert link.type == 'sc'
        assert link.id == url  # SoundCloud uses full URL as ID

    def test_from_url_google_drive(self):
        """Parse Google Drive file URL"""
        url = 'https://drive.google.com/file/d/1A2B3C4D5E6F7G8H/view'
        link = MediaLink.from_url(url)
        assert link.type == 'gd'
        assert link.id == '1A2B3C4D5E6F7G8H'

    def test_from_url_google_drive_open(self):
        """Parse Google Drive open?id= URL"""
        url = 'https://drive.google.com/open?id=1A2B3C4D5E6F7G8H'
        link = MediaLink.from_url(url)
        assert link.type == 'gd'
        assert link.id == '1A2B3C4D5E6F7G8H'

    def test_from_url_google_docs_drive(self):
        """Parse Google Docs domain drive URL"""
        url = 'https://docs.google.com/file/d/1A2B3C4D5E6F7G8H'
        link = MediaLink.from_url(url)
        assert link.type == 'gd'
        assert link.id == '1A2B3C4D5E6F7G8H'

    def test_from_url_imgur_album(self):
        """Parse Imgur album URL"""
        url = 'https://imgur.com/a/AbCdEfG'
        link = MediaLink.from_url(url)
        assert link.type == 'im'
        assert link.id == 'AbCdEfG'

    def test_from_url_streamable(self):
        """Parse Streamable URL"""
        url = 'https://streamable.com/abc123'
        link = MediaLink.from_url(url)
        assert link.type == 'sb'
        assert link.id == 'abc123'

    def test_from_url_vidme(self):
        """Parse Vid.me URL"""
        url = 'https://vid.me/test123'
        link = MediaLink.from_url(url)
        assert link.type == 'vm'
        assert link.id == 'test123'

    def test_from_url_vidme_embedded(self):
        """Parse Vid.me embedded URL"""
        url = 'https://vid.me/embedded/test123'
        link = MediaLink.from_url(url)
        assert link.type == 'vm'
        assert link.id == 'test123'

    def test_from_url_livestream(self):
        """Parse Livestream URL"""
        url = 'https://livestream.com/accounts/channel'
        link = MediaLink.from_url(url)
        assert link.type == 'li'
        assert link.id == 'accounts/channel'

    def test_from_url_ustream(self):
        """Parse Ustream URL"""
        url = 'https://ustream.tv/channel/test'
        link = MediaLink.from_url(url)
        assert link.type == 'us'
        assert link.id == 'channel/test'

    def test_from_url_smashcast(self):
        """Parse Smashcast (formerly Hitbox) URL"""
        url = 'https://smashcast.tv/channelname'
        link = MediaLink.from_url(url)
        assert link.type == 'hb'
        assert link.id == 'channelname'

    def test_from_url_hitbox(self):
        """Parse legacy Hitbox URL"""
        url = 'https://hitbox.tv/channelname'
        link = MediaLink.from_url(url)
        assert link.type == 'hb'
        assert link.id == 'channelname'


class TestFromUrlRawFiles:
    """Test MediaLink.from_url for raw file URLs"""

    def test_from_url_mp4_file(self):
        """Parse HTTPS .mp4 file URL"""
        url = 'https://example.com/videos/sample.mp4'
        link = MediaLink.from_url(url)
        assert link.type == 'fi'
        assert link.id == url

    def test_from_url_webm_file(self):
        """Parse HTTPS .webm file URL"""
        url = 'https://example.com/video.webm'
        link = MediaLink.from_url(url)
        assert link.type == 'fi'
        assert link.id == url

    def test_from_url_mp3_file(self):
        """Parse HTTPS .mp3 file URL"""
        url = 'https://example.com/audio.mp3'
        link = MediaLink.from_url(url)
        assert link.type == 'fi'
        assert link.id == url

    def test_from_url_all_supported_extensions(self):
        """Parse all supported file extensions"""
        extensions = ['.mp4', '.flv', '.webm', '.ogg', '.ogv', '.mp3', '.mov', '.m4a']
        for ext in extensions:
            url = f'https://example.com/file{ext}'
            link = MediaLink.from_url(url)
            assert link.type == 'fi'
            assert link.id == url

    def test_from_url_m3u8_stream(self):
        """Parse M3U8 stream URL"""
        url = 'https://example.com/stream/playlist.m3u8'
        link = MediaLink.from_url(url)
        assert link.type == 'hl'
        assert link.id == url

    def test_from_url_json_custom_embed(self):
        """Parse .json URL for custom embed"""
        url = 'https://example.com/embed/config.json'
        link = MediaLink.from_url(url)
        assert link.type == 'cm'
        assert link.id == url

    def test_from_url_http_file_rejected(self):
        """Reject HTTP (non-HTTPS) raw file URL"""
        url = 'http://example.com/video.mp4'
        with pytest.raises(ValueError, match='Raw files must begin with "https"'):
            MediaLink.from_url(url)

    def test_from_url_unsupported_extension(self):
        """Reject HTTPS file with unsupported extension"""
        url = 'https://example.com/file.avi'
        with pytest.raises(ValueError, match='does not match the supported file extensions'):
            MediaLink.from_url(url)

    def test_from_url_https_no_extension(self):
        """Reject HTTPS URL with no file extension"""
        url = 'https://example.com/somepath'
        with pytest.raises(ValueError, match='does not match the supported file extensions'):
            MediaLink.from_url(url)


class TestFromUrlCustomTypes:
    """Test MediaLink.from_url for custom type prefixes"""

    def test_from_url_dm_prefix(self):
        """Parse dm: prefix for Dailymotion direct"""
        url = 'dm:x7tgad0'
        link = MediaLink.from_url(url)
        assert link.type == 'dm'
        assert link.id == 'x7tgad0'

    def test_from_url_fi_prefix(self):
        """Parse fi: prefix for file direct"""
        url = 'fi:https://example.com/video.mp4'
        link = MediaLink.from_url(url)
        assert link.type == 'fi'
        assert link.id == 'https://example.com/video.mp4'

    def test_from_url_cm_prefix(self):
        """Parse cm: prefix for custom embed"""
        url = 'cm:https://example.com/embed.json'
        link = MediaLink.from_url(url)
        assert link.type == 'cm'
        assert link.id == 'https://example.com/embed.json'

    def test_from_url_generic_prefix(self):
        """Parse generic XX:id format"""
        url = 'ab:test123'
        link = MediaLink.from_url(url)
        assert link.type == 'ab'
        assert link.id == 'test123'

    def test_from_url_generic_prefix_with_special_chars(self):
        """Parse generic prefix with special characters in ID"""
        url = 'zz:path/to/resource?param=value'
        link = MediaLink.from_url(url)
        assert link.type == 'zz'
        assert link.id == 'path/to/resource?param=value'


class TestFromUrlEdgeCases:
    """Test MediaLink.from_url edge cases"""

    def test_from_url_rtmp_stream(self):
        """Parse RTMP stream URL"""
        url = 'rtmp://example.com/live/stream'
        link = MediaLink.from_url(url)
        assert link.type == 'rt'
        assert link.id == url

    def test_from_url_with_whitespace(self):
        """Parse URL with leading/trailing whitespace"""
        url = '  https://youtube.com/watch?v=dQw4w9WgXcQ  '
        link = MediaLink.from_url(url)
        assert link.type == 'yt'
        assert link.id == 'dQw4w9WgXcQ'

    def test_from_url_with_fragment(self):
        """Parse URL with fragment identifier (#)"""
        url = 'https://youtube.com/watch?v=dQw4w9WgXcQ#t=42'
        link = MediaLink.from_url(url)
        assert link.type == 'yt'
        assert link.id == 'dQw4w9WgXcQ'

    def test_from_url_case_insensitive_domain(self):
        """Parse URL with mixed case domain"""
        url = 'https://YouTube.com/watch?v=dQw4w9WgXcQ'
        link = MediaLink.from_url(url)
        assert link.type == 'yt'
        assert link.id == 'dQw4w9WgXcQ'

    def test_from_url_priority_order(self):
        """Verify patterns are matched in order (first match wins)"""
        # dm: prefix should match before URL patterns
        url = 'dm:test'
        link = MediaLink.from_url(url)
        assert link.type == 'dm'
        assert link.id == 'test'

    def test_from_url_empty_string(self):
        """Parse empty string raises ValueError"""
        with pytest.raises(ValueError):
            MediaLink.from_url('')

    def test_from_url_invalid_scheme(self):
        """Parse URL with invalid scheme (not https/rtmp) for non-provider"""
        url = 'ftp://example.com/file.mp4'
        with pytest.raises(ValueError):
            MediaLink.from_url(url)


class TestMediaLinkIntegration:
    """Integration tests for MediaLink URL round-trips"""

    def test_roundtrip_youtube(self):
        """Parse YouTube URL and convert back"""
        original_url = 'https://youtube.com/watch?v=dQw4w9WgXcQ'
        link = MediaLink.from_url(original_url)
        reconstructed = link.url
        assert reconstructed == original_url

    def test_roundtrip_twitch_channel(self):
        """Parse Twitch channel and convert back"""
        original_url = 'https://twitch.tv/ninja'
        link = MediaLink.from_url(original_url)
        reconstructed = link.url
        assert reconstructed == original_url

    def test_roundtrip_vimeo(self):
        """Parse Vimeo URL and convert back"""
        original_url = 'https://vimeo.com/123456789'
        link = MediaLink.from_url(original_url)
        reconstructed = link.url
        assert reconstructed == original_url

    def test_roundtrip_raw_file(self):
        """Parse raw file URL and convert back"""
        original_url = 'https://example.com/video.mp4'
        link = MediaLink.from_url(original_url)
        reconstructed = link.url
        assert reconstructed == original_url

    def test_roundtrip_m3u8(self):
        """Parse M3U8 stream and convert back"""
        original_url = 'https://example.com/stream.m3u8'
        link = MediaLink.from_url(original_url)
        reconstructed = link.url
        assert reconstructed == original_url

    def test_from_string_representation(self):
        """Create link, convert to string, and recreate"""
        link1 = MediaLink('yt', 'dQw4w9WgXcQ')
        string_rep = str(link1)
        assert string_rep == 'yt:dQw4w9WgXcQ'
        # Can parse custom format if needed
        link2 = MediaLink.from_url(string_rep)
        assert link2.type == 'yt'
        assert link2.id == 'dQw4w9WgXcQ'
```

## Coverage Analysis

| Component | Expected Coverage | Justification |
|-----------|------------------|---------------|
| MediaLink.__init__ | 100% | 4 tests: basic, different types, empty ID, special chars |
| MediaLink.__str__ | 100% | 2 tests: basic format, various types |
| MediaLink.__repr__ | 100% | 1 test: constructor format |
| MediaLink.__eq__ | 100% | 4 tests: equality, different ID/type, different class |
| MediaLink.url property | 100% | 10 tests: all major types, unknown type warning |
| MediaLink.from_url | 95% | 50+ tests covering all URL patterns |
| YouTube parsing | 100% | 6 tests: watch, short, timestamp, embedded, playlist, query params |
| Twitch parsing | 100% | 5 tests: clips, videos, channels, legacy format, special chars |
| Other providers | 100% | 14 tests: all supported providers |
| Raw files | 100% | 10 tests: all extensions, M3U8, JSON, HTTP rejection, unsupported ext |
| Custom types | 100% | 5 tests: dm:, fi:, cm:, generic XX: |
| Edge cases | 100% | 7 tests: RTMP, whitespace, fragments, case, priority, empty, invalid |
| Integration | 100% | 6 tests: round-trip conversions |

**Overall Expected Coverage**: 97%

## Manual Verification

### Run Tests

```bash
# Run media_link tests only
pytest tests/unit/test_media_link.py -v

# Run with coverage
pytest tests/unit/test_media_link.py --cov=lib.media_link --cov-report=term-missing

# Run specific test class
pytest tests/unit/test_media_link.py::TestFromUrlYoutube -v

# Run edge case tests
pytest tests/unit/test_media_link.py::TestFromUrlEdgeCases -v
```

### Expected Output

```
tests/unit/test_media_link.py::TestMediaLinkInit::test_init_basic PASSED
tests/unit/test_media_link.py::TestFromUrlYoutube::test_from_url_youtube_watch PASSED
tests/unit/test_media_link.py::TestFromUrlYoutube::test_from_url_youtube_short PASSED
[... 80+ more tests ...]
tests/unit/test_media_link.py::TestMediaLinkIntegration::test_from_string_representation PASSED

---------- coverage: platform win32, python 3.x -----------
Name                  Stmts   Miss  Cover   Missing
---------------------------------------------------
lib/media_link.py       85      2    97%   67, 142
---------------------------------------------------
TOTAL                   85      2    97%
```

### Sample Test Execution

```python
# Test URL parsing
from lib.media_link import MediaLink

# YouTube
link = MediaLink.from_url('https://youtube.com/watch?v=dQw4w9WgXcQ')
assert link.type == 'yt'
assert link.id == 'dQw4w9WgXcQ'
assert link.url == 'https://youtube.com/watch?v=dQw4w9WgXcQ'

# Twitch
link = MediaLink.from_url('https://twitch.tv/ninja')
assert link.type == 'tw'
assert link.id == 'ninja'

# Raw file
link = MediaLink.from_url('https://example.com/video.mp4')
assert link.type == 'fi'
assert link.id == 'https://example.com/video.mp4'

# Error handling
try:
    MediaLink.from_url('http://example.com/video.mp4')
    assert False, "Should have raised ValueError"
except ValueError as e:
    assert 'https' in str(e)
```

## Success Criteria

- [ ] All 85+ tests pass
- [ ] Coverage ≥ 95% for lib/media_link.py
- [ ] All 24 URL patterns tested
- [ ] All supported providers work correctly
- [ ] Error handling for invalid URLs works
- [ ] HTTPS validation for raw files enforced
- [ ] Round-trip conversions (URL → MediaLink → URL) work
- [ ] No regression in existing functionality

## Dependencies
- SPEC-Commit-1: Test infrastructure (conftest.py, pytest.ini)

## Next Steps
After completing media_link tests:
1. Proceed to SPEC-Commit-5: lib/playlist.py Tests
2. Verify MediaLink is used correctly in channel/bot modules
3. Consider adding tests for future media providers if needed
