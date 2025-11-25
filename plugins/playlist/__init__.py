"""
Playlist Plugin

Manages media playlists for channels with queue operations,
voting, and persistence.

This plugin migrates the core playlist functionality from lib/playlist.py
to the modern NATS-based plugin architecture.
"""

from .plugin import PlaylistPlugin

__all__ = ["PlaylistPlugin"]
__version__ = "1.0.0"
