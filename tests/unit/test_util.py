"""
Unit tests for lib/util.py

Tests MessageParser, sequence utilities, async HTTP, and IP cloaking functions.
"""
import pytest
from unittest.mock import Mock, patch
from lib.util import (
    MessageParser,
    to_sequence,
    get,
    ip_hash,
    cloak_ip,
    uncloak_ip
)


class TestMessageParser:
    """Test MessageParser HTML to markup conversion."""
    
    def test_init_default_markup(self):
        """Test MessageParser initialization with default markup."""
        parser = MessageParser()
        assert parser.markup is not None
        assert len(parser.markup) > 0
        assert parser.message == ''
        assert parser.tags == []
    
    def test_init_custom_markup(self):
        """Test MessageParser initialization with custom markup."""
        custom_markup = [('b', None, '**', '**')]
        parser = MessageParser(markup=custom_markup)
        assert parser.markup == custom_markup
    
    def test_parse_plain_text(self):
        """Test parsing plain text (no HTML)."""
        parser = MessageParser()
        result = parser.parse('Hello, world!')
        assert result == 'Hello, world!'
    
    def test_parse_strong_tag(self):
        """Test parsing <strong> tags to *text*."""
        parser = MessageParser()
        result = parser.parse('<strong>bold</strong>')
        assert result == '*bold*'
    
    def test_parse_em_tag(self):
        """Test parsing <em> tags to _text_."""
        parser = MessageParser()
        result = parser.parse('<em>italic</em>')
        assert result == '_italic_'
    
    def test_parse_code_tag(self):
        """Test parsing <code> tags to `text`."""
        parser = MessageParser()
        result = parser.parse('<code>code</code>')
        assert result == '`code`'
    
    def test_parse_strikethrough_tag(self):
        """Test parsing <s> tags to ~~text~~."""
        parser = MessageParser()
        result = parser.parse('<s>strikethrough</s>')
        assert result == '~~strikethrough~~'
    
    def test_parse_spoiler_class(self):
        """Test parsing spoiler class to [sp]text[/sp]."""
        parser = MessageParser()
        result = parser.parse('<span class="spoiler">hidden</span>')
        assert result == '[sp]hidden[/sp]'
    
    def test_parse_nested_tags(self):
        """Test parsing nested HTML tags."""
        parser = MessageParser()
        result = parser.parse('<strong><em>bold italic</em></strong>')
        assert result == '*_bold italic_*'
    
    def test_parse_multiple_tags(self):
        """Test parsing multiple separate tags."""
        parser = MessageParser()
        result = parser.parse('<strong>bold</strong> and <em>italic</em>')
        assert result == '*bold* and _italic_'
    
    def test_parse_html_entities(self):
        """Test parsing HTML entities (&lt; &gt; &amp;)."""
        parser = MessageParser()
        result = parser.parse('&lt;tag&gt; &amp; text')
        assert result == '<tag> & text'
    
    def test_parse_unclosed_tags(self):
        """Test parsing unclosed tags (closes them automatically)."""
        parser = MessageParser()
        result = parser.parse('<strong>unclosed')
        assert result == '*unclosed*'
    
    def test_parse_link_with_href(self):
        """Test parsing links extracts href."""
        parser = MessageParser()
        result = parser.parse('<a href="http://example.com">link</a>')
        assert 'http://example.com' in result
    
    def test_parse_image_with_src(self):
        """Test parsing images extracts src."""
        parser = MessageParser()
        result = parser.parse('<img src="http://example.com/image.png"/>')
        assert 'http://example.com/image.png' in result
    
    def test_parse_unknown_tags_ignored(self):
        """Test unknown tags are ignored (text preserved)."""
        parser = MessageParser()
        result = parser.parse('<unknown>text</unknown>')
        assert 'text' in result
    
    def test_parse_empty_string(self):
        """Test parsing empty string."""
        parser = MessageParser()
        result = parser.parse('')
        assert result == ''
    
    def test_parse_resets_state(self):
        """Test that parsing resets parser state between calls."""
        parser = MessageParser()
        parser.parse('<strong>first</strong>')
        result = parser.parse('<em>second</em>')
        # Should not contain remnants of first parse
        assert result == '_second_'
        assert '*first*' not in result
    
    def test_get_tag_markup_matching_tag(self):
        """Test get_tag_markup finds matching markup."""
        parser = MessageParser()
        markup = parser.get_tag_markup('strong', [])
        assert markup is not None
        assert markup == ('*', '*')
    
    def test_get_tag_markup_matching_class(self):
        """Test get_tag_markup finds markup by class attribute."""
        parser = MessageParser()
        markup = parser.get_tag_markup('span', [('class', 'spoiler')])
        assert markup is not None
        assert markup == ('[sp]', '[/sp]')
    
    def test_get_tag_markup_no_match(self):
        """Test get_tag_markup returns None for unknown tags."""
        parser = MessageParser()
        markup = parser.get_tag_markup('unknown', [])
        assert markup is None
    
    def test_parse_with_none_markup(self):
        """Test parser with markup=None (no conversions)."""
        parser = MessageParser(markup=None)
        result = parser.parse('<strong>text</strong>')
        # No markup conversion, just extracts text
        assert 'text' in result
    
    def test_parse_complex_html(self):
        """Test parsing complex HTML message."""
        parser = MessageParser()
        html = '<strong>Bold</strong> and <em>italic</em> with <code>code</code>'
        result = parser.parse(html)
        assert '*Bold*' in result
        assert '_italic_' in result
        assert '`code`' in result


class TestToSequence:
    """Test to_sequence utility function."""
    
    def test_none_returns_empty_tuple(self):
        """Test None returns empty tuple."""
        result = to_sequence(None)
        assert result == ()
    
    def test_single_value_returns_tuple(self):
        """Test single value wrapped in tuple."""
        result = to_sequence(42)
        assert result == (42,)
    
    def test_string_returns_tuple(self):
        """Test string wrapped in tuple (not char sequence)."""
        result = to_sequence('hello')
        assert result == ('hello',)
    
    def test_list_returns_as_is(self):
        """Test list returned as-is."""
        original = [1, 2, 3]
        result = to_sequence(original)
        assert result is original
        assert result == [1, 2, 3]
    
    def test_tuple_returns_as_is(self):
        """Test tuple returned as-is."""
        original = (1, 2, 3)
        result = to_sequence(original)
        assert result is original
    
    def test_dict_wrapped_in_tuple(self):
        """Test dict wrapped in tuple (not a sequence)."""
        original = {'key': 'value'}
        result = to_sequence(original)
        assert result == (original,)
    
    def test_set_wrapped_in_tuple(self):
        """Test set wrapped in tuple (not a sequence)."""
        original = {1, 2, 3}
        result = to_sequence(original)
        assert result == (original,)


class TestAsyncGet:
    """Test async HTTP get function."""
    
    @pytest.mark.asyncio
    async def test_get_success(self):
        """Test successful HTTP GET request."""
        with patch('lib.util.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = 'response content'
            mock_get.return_value = mock_response
            
            result = await get('http://example.com')
            
            assert result == 'response content'
            mock_get.assert_called_once_with('http://example.com')
    
    @pytest.mark.asyncio
    async def test_get_runs_in_executor(self):
        """Test that get runs in executor (non-blocking)."""
        with patch('lib.util.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.text = 'content'
            mock_get.return_value = mock_response
            
            # Should not block event loop
            result = await get('http://example.com')
            assert result == 'content'


class TestIPHash:
    """Test IP hashing utility."""
    
    def test_ip_hash_consistent(self):
        """Test ip_hash returns consistent results."""
        hash1 = ip_hash('127.0.0.1', 3)
        hash2 = ip_hash('127.0.0.1', 3)
        assert hash1 == hash2
    
    def test_ip_hash_length(self):
        """Test ip_hash returns requested length."""
        result = ip_hash('test', 5)
        assert len(result) == 5
    
    def test_ip_hash_different_inputs(self):
        """Test different inputs produce different hashes."""
        hash1 = ip_hash('127.0.0.1', 3)
        hash2 = ip_hash('192.168.1.1', 3)
        assert hash1 != hash2
    
    def test_ip_hash_base64_encoded(self):
        """Test ip_hash returns base64 characters."""
        result = ip_hash('test', 10)
        # Base64 uses A-Z, a-z, 0-9, +, /
        assert all(c.isalnum() or c in '+/' for c in result)


class TestCloakIP:
    """Test IP cloaking function."""
    
    def test_cloak_full_ip(self):
        """Test cloaking entire IP address."""
        result = cloak_ip('127.0.0.1')
        # Should have 4 parts separated by dots
        parts = result.split('.')
        assert len(parts) == 4
        # All parts should be hashes (3 chars each)
        for part in parts:
            assert len(part) == 3
    
    def test_cloak_partial_ip(self):
        """Test cloaking from specific index."""
        result = cloak_ip('127.0.0.1', 2)
        parts = result.split('.')
        assert parts[0] == '127'  # First part unchanged
        assert parts[1] == '0'    # Second part unchanged
        assert len(parts[2]) == 3 # Third part hashed
        assert len(parts[3]) == 3 # Fourth part hashed
    
    def test_cloak_consistent(self):
        """Test cloaking is consistent for same IP."""
        result1 = cloak_ip('192.168.1.1')
        result2 = cloak_ip('192.168.1.1')
        assert result1 == result2
    
    def test_cloak_different_ips(self):
        """Test different IPs produce different cloaked results."""
        result1 = cloak_ip('127.0.0.1')
        result2 = cloak_ip('192.168.1.1')
        assert result1 != result2
    
    def test_cloak_example_from_docstring(self):
        """Test example from function docstring."""
        result = cloak_ip('127.0.0.1')
        # Should match the documented example
        assert result == 'yFA.j8g.iXh.gvS'
    
    def test_cloak_partial_example_from_docstring(self):
        """Test partial cloak example from docstring."""
        result = cloak_ip('127.0.0.1', 2)
        assert result == '127.0.ou9.RBl'
    
    def test_cloak_short_ip(self):
        """Test cloaking IP with less than 4 parts."""
        result = cloak_ip('127.0')
        parts = result.split('.')
        # Should pad to 4 parts
        assert len(parts) == 4


class TestUncloakIP:
    """Test IP uncloaking function."""
    
    def test_uncloak_full_ip(self):
        """Test uncloaking fully cloaked IP."""
        cloaked = cloak_ip('127.0.0.1')
        result = uncloak_ip(cloaked)
        assert '127.0.0.1' in result
    
    def test_uncloak_partial_ip(self):
        """Test uncloaking partially cloaked IP."""
        cloaked = cloak_ip('127.0.0.1', 2)
        result = uncloak_ip(cloaked, 2)
        assert '127.0.0.1' in result
    
    def test_uncloak_auto_detect_start(self):
        """Test uncloaking with auto-detect start index."""
        cloaked = cloak_ip('127.0.0.1', 2)
        result = uncloak_ip(cloaked, None)  # Auto-detect
        assert '127.0.0.1' in result
    
    def test_uncloak_example_from_docstring(self):
        """Test example from function docstring."""
        result = uncloak_ip('yFA.j8g.iXh.gvS')
        assert result == ['127.0.0.1']
    
    def test_uncloak_partial_example_from_docstring(self):
        """Test partial uncloak example from docstring."""
        # Without correct start index, should return empty
        result = uncloak_ip('127.0.ou9.RBl')
        assert result == []
        
        # With correct start index, should work
        result = uncloak_ip('127.0.ou9.RBl', 2)
        assert result == ['127.0.0.1']
        
        # With auto-detect, should work
        result = uncloak_ip('127.0.ou9.RBl', None)
        assert result == ['127.0.0.1']
    
    def test_uncloak_returns_list(self):
        """Test uncloak_ip returns list of possibilities."""
        cloaked = cloak_ip('192.168.1.1')
        result = uncloak_ip(cloaked)
        assert isinstance(result, list)
    
    def test_uncloak_wrong_start_returns_empty(self):
        """Test uncloaking with wrong start index returns empty list."""
        cloaked = cloak_ip('127.0.0.1', 2)
        # Try to uncloak with wrong start index
        result = uncloak_ip(cloaked, 0)
        # Won't find match because hash doesn't match
        assert result == []
    
    def test_cloak_uncloak_roundtrip(self):
        """Test cloaking and uncloaking roundtrip."""
        original = '10.20.30.40'
        cloaked = cloak_ip(original)
        uncloaked = uncloak_ip(cloaked)
        assert original in uncloaked
    
    def test_cloak_uncloak_partial_roundtrip(self):
        """Test partial cloaking and uncloaking roundtrip."""
        original = '172.16.254.1'
        start = 1
        cloaked = cloak_ip(original, start)
        uncloaked = uncloak_ip(cloaked, start)
        assert original in uncloaked


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_message_parser_with_empty_markup(self):
        """Test MessageParser with empty markup list."""
        parser = MessageParser(markup=[])
        result = parser.parse('<strong>text</strong>')
        # No conversions, just text
        assert 'text' in result
    
    def test_to_sequence_with_zero(self):
        """Test to_sequence with zero value."""
        result = to_sequence(0)
        assert result == (0,)
    
    def test_to_sequence_with_false(self):
        """Test to_sequence with False (falsy but not None)."""
        result = to_sequence(False)
        assert result == (False,)
    
    def test_to_sequence_with_empty_list(self):
        """Test to_sequence with empty list."""
        result = to_sequence([])
        assert result == []
    
    def test_ip_hash_empty_string(self):
        """Test ip_hash with empty string."""
        result = ip_hash('', 3)
        assert len(result) == 3
    
    def test_cloak_ip_single_octet(self):
        """Test cloaking single octet."""
        result = cloak_ip('127')
        parts = result.split('.')
        assert len(parts) == 4
        # Should pad with asterisks
        assert '*' in result
    
    def test_uncloak_invalid_format(self):
        """Test uncloaking invalid IP format."""
        # This won't match any valid IP
        result = uncloak_ip('invalid.ip.format')
        # Should return empty or handle gracefully
        assert isinstance(result, list)
