# Import version from project root
import sys
from pathlib import Path

from .bot import Bot
from .channel import Channel
from .connection import ConnectionAdapter
from .media_link import MediaLink
from .proxy import set_proxy
from .socket_io import SocketIO
from .storage import SQLiteStorage, StorageAdapter
from .user import User
from .util import MessageParser

sys.path.insert(0, str(Path(__file__).parent.parent))
from __version__ import __version__
