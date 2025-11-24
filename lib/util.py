#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
from base64 import b64encode
from collections.abc import Sequence
from hashlib import md5
from html import unescape
from html.parser import HTMLParser
from itertools import islice

import requests  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


# Compatibility for older Python versions that don't have task_done in asyncio.Queue
if hasattr(asyncio.Queue, 'task_done'):
    Queue = asyncio.Queue
else:
    # Wrapper to add task_done and join methods for older Python versions
    class Queue(asyncio.Queue):  # type: ignore[no-redef]
        def task_done(self):
            logger.debug('task_done %s', self)

        async def join(self):
            logger.info('join %s', self)

# Compatibility for getting current task (different in Python 3.6 vs 3.7+)
try:
    current_task = asyncio.current_task
except AttributeError:
    current_task = asyncio.Task.current_task  # type: ignore[attr-defined]


class MessageParser(HTMLParser):
    """Chat message parser.

    Attributes
    ----------
    markup : `None` or `list` of (`str`, `None` or `dict` of (`str`, `str`), `None` or `str`, `None` or `str`)
    message : `str`
    tags : `list` of (`str`, `str`)
    """

    DEFAULT_MARKUP = [
        ('code', None, '`', '`'),
        ('strong', None, '*', '*'),
        ('em', None, '_', '_'),
        ('s', None, '~~', '~~'),
        (None, {'class': 'spoiler'}, '[sp]', '[/sp]')
    ]

    def __init__(self, markup=DEFAULT_MARKUP):
        super().__init__()
        self.markup = markup
        self.message = ''
        self.tags = []

    def get_tag_markup(self, tag, attr):
        """Get markup delimiters for a given HTML tag and attributes

        Args:
            tag: HTML tag name (e.g., 'strong', 'em')
            attr: List of (name, value) tuples for tag attributes

        Returns:
            Tuple of (start_markup, end_markup) or None if no match
        """
        if self.markup is None:
            return None

        # Convert attribute list to dict for easier lookup
        attr = dict(attr)

        # Search for matching markup definition
        for tag_, attr_, start, end in self.markup:
            # Check if tag matches (None means any tag)
            if tag_ is not None and tag_ != tag:
                continue

            # Check if attributes match (None means any attributes)
            if attr_ is not None:
                match = True
                for name, value in attr_.items():
                    if attr.get(name, None) != value:
                        match = False
                        break
                if not match:
                    continue

            # Found a match
            return start, end

    def handle_starttag(self, tag, attr):
        """Handle opening HTML tags by converting to markup syntax

        Args:
            tag: HTML tag name
            attr: List of (name, value) tuples for attributes
        """
        markup = self.get_tag_markup(tag, attr)
        if markup is not None:
            start, end = markup
            # Add opening delimiter if specified
            if start is not None:
                self.message += start
            # Push closing delimiter onto stack if specified
            if end is not None:
                self.tags.append((tag, end))
        else:
            # For unrecognized tags, extract URLs from src/href attributes
            for name, value in attr:
                if name in ('src', 'href'):
                    self.message += ' %s ' % value

    def handle_endtag(self, tag):
        """Handle closing HTML tags by adding closing markup

        Args:
            tag: HTML tag name
        """
        # Pop tags from stack until we find the matching opening tag
        while self.tags:
            tag_, end = self.tags.pop()
            self.message += end
            if tag_ == tag:
                return

    def handle_data(self, data):
        """Handle text data between HTML tags

        Args:
            data: Text content
        """
        # Unescape HTML entities (e.g., &lt; -> <)
        self.message += unescape(data)

    def parse(self, msg):
        """Parse a message.

        Parameters
        ----------
        msg : `str`
            Message to parse.

        Returns
        -------
        `str`
            Parsed message.
        """
        # Reset parser state
        self.message = ''
        self.tags = []

        # Parse the HTML
        self.feed(msg)
        self.close()
        self.reset()

        # Close any unclosed tags
        for _, end in reversed(self.tags):
            self.message += end

        return self.message


def to_sequence(obj):
    """Convert an object to sequence.

    Parameters
    ----------
    obj : `object`

    Returns
    -------
    `collections.Sequence`

    Examples
    --------
    >>> to_sequence(None)
    ()
    >>> to_sequence(1)
    (1,)
    >>> to_sequence('str')
    ('str',)
    >>> x = [0, 1, 2]
    >>> to_sequence(x)
    [0, 1, 2]
    >>> to_sequence(x) is x
    True
    """
    if obj is None:
        return ()
    if isinstance(obj, str) or not isinstance(obj, Sequence):
        return (obj,)
    return obj


async def get(url):
    """Asynchronous HTTP GET request.

    Parameters
    ----------
    url: `str`

    Returns
    -------
    `str`
    """
    # Run blocking requests.get in executor to avoid blocking event loop
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: requests.get(url).text)


def ip_hash(string, length):
    """Generate a hash for IP cloaking

    Args:
        string: String to hash
        length: Length of resulting hash

    Returns:
        Base64-encoded MD5 hash truncated to length
    """
    res = md5(string.encode('utf-8')).digest()
    return b64encode(res)[:length].decode('utf-8')


def cloak_ip(ip, start=0):
    """Cloak IP.

    Parameters
    ----------
    ip : `str`
        IP to cloak.
    start : `int`, optional
        Index of first cloaked part (0-3).

    Returns
    -------
    `str`

    Examples
    --------
    >>> cloak_ip('127.0.0.1')
    'yFA.j8g.iXh.gvS'
    >>> cloak_ip('127.0.0.1', 2)
    '127.0.ou9.RBl'
    """
    parts = ip.split('.')
    acc = ''  # Accumulator for building hash input

    # Hash each part starting from 'start' index
    for i, part in islice(enumerate(parts), start, None):
        # Replace part with hash based on accumulated previous parts
        parts[i] = ip_hash('%s%s%s' % (acc, part, i), 3)
        acc += part  # Add current part to accumulator

    # Pad with asterisks if less than 4 parts
    while len(parts) < 4:
        parts.append('*')

    return '.'.join(parts)


def _uncloak_ip(cloaked_parts, uncloaked_parts, acc, i, ret):
    """Recursive helper to brute-force uncloak IP addresses

    Args:
        cloaked_parts: List of cloaked IP parts (hashes or plain)
        uncloaked_parts: Working list being built with uncloaked parts
        acc: Accumulator string of previous parts for hash calculation
        i: Current index being processed (0-3)
        ret: List to append successful uncloaked IPs to
    """
    # Base case: processed all 4 parts
    if i > 3:
        ret.append('.'.join(uncloaked_parts))
        return

    # Try all possible values (0-255) for this octet
    for part in range(256):
        part_hash = ip_hash('%s%s%s' % (acc, part, i), 3)
        # If hash matches, this is a valid candidate
        if part_hash == cloaked_parts[i]:
            uncloaked_parts[i] = str(part)
            # Recursively process next part
            _uncloak_ip(
                cloaked_parts,
                uncloaked_parts,
                '%s%d' % (acc, part),
                i + 1,
                ret
            )

def uncloak_ip(ip, start=0):
    """Uncloak IP.

    Parameters
    ----------
    ip : `str`
        Cloaked IP.
    start : `int` or `None`, optional
        Index of first cloaked part (0-3) (`None` - detect).

    Returns
    -------
    `list` of `str`

    Examples
    --------
    >>> uncloak_ip('yFA.j8g.iXh.gvS')
    ['127.0.0.1']
    >>> uncloak_ip('127.0.ou9.RBl')
    []
    >>> uncloak_ip('127.0.ou9.RBl', 2)
    ['127.0.0.1']
    >>> uncloak_ip('127.0.ou9.RBl', None)
    ['127.0.0.1']
    """
    parts = ip.split('.')

    # Auto-detect start index if None
    if start is None:
        for start, part in enumerate(parts):
            try:
                val = int(part)
                # If not a valid IP octet, this is where cloaking starts
                if val < 0 or val > 255:
                    break
            except ValueError:
                # Not an integer, cloaking starts here
                break

    # Brute-force uncloak by trying all possible values
    ret = []
    _uncloak_ip(parts, list(parts), '', start, ret)
    return ret
