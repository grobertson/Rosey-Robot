#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import json
import logging
import asyncio
import collections
from typing import Optional

from .error import (
    CytubeError,
    SocketConfigError, LoginError,
    ChannelError, ChannelPermissionError, Kicked
)
from .connection import ConnectionAdapter, CyTubeConnection
from .connection.errors import ConnectionError as ConnError, NotConnectedError
from .channel import Channel
from .user import User
from .playlist import PlaylistItem
from .media_link import MediaLink
from .util import get as default_get, to_sequence

try:
    from common.database import BotDatabase
except ImportError:
    BotDatabase = None


class Bot:
    """CyTube bot.

    Attributes
    ----------
    get : `function` (url, loop)
        HTTP GET coroutine.
    socket_io : `function` (url, loop)
        socket.io connect coroutine.
    response_timeout : `float`
        socket.io event response timeout in seconds.
    restart_delay : `None` or `float`
        Delay in seconds before reconnection.
        `None` or < 0 - do not reconnect.
    domain : `str`
        Domain.
    channel : `cytube_bot.channel.Channel`
        Channel.
    user : `cytube_bot.user.User`
        Bot user.
    server : `None` or `str`
        socket.io server URL.
    socket : `None` or `cytube_bot.socket_io.SocketIO`
        socket.io connection.
    handlers : `collections.defaultdict` of (`str`, `list` of `function`)
        Event handlers.
    """
    logger = logging.getLogger(__name__)

    # Kept for backward compatibility with CyTube-specific operations
    SOCKET_CONFIG_URL = '%(domain)s/socketconfig/%(channel)s.json'
    SOCKET_IO_URL = '%(domain)s/socket.io/'

    GUEST_LOGIN_LIMIT = re.compile(r'guest logins .* ([0-9]+) seconds\.', re.I)
    MUTED = re.compile(r'.*\bmuted', re.I)

    EVENT_LOG_LEVEL = {
        'mediaUpdate': logging.DEBUG,
        'channelCSSJS': logging.DEBUG,
        'emoteList': logging.DEBUG,
        # Normalized events
        'message': logging.INFO,
        'user_join': logging.INFO,
        'user_leave': logging.INFO,
        'user_list': logging.INFO,
        'pm': logging.INFO
    }

    EVENT_LOG_LEVEL_DEFAULT = logging.INFO

    @classmethod
    def from_cytube(cls, domain: str, channel: str,
                    channel_password: Optional[str] = None,
                    user: Optional[str] = None,
                    password: Optional[str] = None,
                    **kwargs):
        """
        Create Bot with CyTube connection (backward compatibility helper).
        
        Parameters
        ----------
        domain : str
            CyTube server domain
        channel : str
            Channel name
        channel_password : str, optional
            Optional channel password
        user : str, optional
            Optional username (guest or registered)
        password : str, optional
            Optional user password (for registered users)
        **kwargs : optional
            Additional Bot options (restart_delay, db_path, enable_db)
        
        Returns
        -------
        Bot
            Bot instance configured for CyTube
        
        Example
        -------
        >>> bot = Bot.from_cytube('https://cytu.be', 'mychannel',
        ...                       user='botname', password='secret')
        >>> await bot.run()
        """
        connection = CyTubeConnection(
            domain=domain,
            channel=channel,
            channel_password=channel_password,
            user=user,
            password=password
        )
        
        # Set channel info from connection (for backward compatibility)
        instance = cls(connection=connection, **kwargs)
        instance.channel.name = channel
        instance.channel.password = channel_password or ''
        if user:
            instance.user.name = user
            instance.user.password = password or ''
        
        return instance

    def __init__(self, connection: ConnectionAdapter,
                 nats_client,
                 restart_delay: float = 5.0):
        """
        Initialize bot with connection adapter and NATS event bus.
        
        ⚠️ BREAKING CHANGE (Sprint 9 Sortie 5):
        - The `db`, `db_path`, and `enable_db` parameters have been REMOVED
        - `nats_client` is now REQUIRED (second parameter, not optional)
        - All database operations now go through NATS event bus
        - DatabaseService must be started separately
        
        Parameters
        ----------
        connection : ConnectionAdapter
            Connection adapter for chat platform.
        nats_client : NATS client
            NATS client for event bus communication (REQUIRED).
            Bot cannot operate without NATS. All database operations
            publish events to NATS subjects.
        restart_delay : float, optional
            Delay in seconds before reconnection.
            0 or negative - do not reconnect.
            
        Raises
        ------
        ValueError
            If nats_client is None. NATS is mandatory in Sprint 9+.
            
        See Also
        --------
        docs/sprints/active/9-The-Accountant/MIGRATION.md : Migration guide
        common.database_service.DatabaseService : Database event bus subscriber
        
        Notes
        -----
        Migration from pre-Sprint 9:
        
        Old (v1)::
        
            bot = Bot(connection, db=database, nats_client=nats)
            
        New (v2)::
        
            bot = Bot(connection, nats_client=nats)
            # DatabaseService runs separately
        """
        import time
        
        # Validate NATS client (REQUIRED)
        if nats_client is None:
            raise ValueError(
                "NATS client is required. Bot cannot operate without NATS event bus. "
                "See docs/sprints/active/9-The-Accountant/MIGRATION.md for migration guide."
            )
        
        self.connection = connection
        self.restart_delay = restart_delay
        self.channel = Channel()
        self.user = User()
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
        self.handlers = collections.defaultdict(list)
        self.start_time = time.time()  # Track bot start time
        self.connect_time = None  # Track connection time
        self._history_task = None  # Background task for logging user counts
        self._status_task = None  # Background task for updating status
        self._outbound_task = None  # Background task for sending messages
        self._maintenance_task = None  # Background task for DB maintenance

        # Store NATS client for event bus communication (REQUIRED)
        self.nats = nats_client
        self.logger.info('NATS event bus enabled')
        
        # NO self.db - Database operations go through NATS only
        # DatabaseService subscribes to NATS subjects separately

        # Register event handlers
        for attr in dir(self):
            if attr.startswith('_on_'):
                event_name = attr[4:]
                self.on(event_name, getattr(self, attr))
                # Also register handler with connection adapter
                self.connection.on_event(event_name, getattr(self, attr))

    @property
    def socket(self):
        """
        Access underlying socket for CyTube-specific operations.
        
        This property provides backward compatibility for CyTube-specific
        methods that need direct socket access (playlist control, etc.).
        
        Returns None if connection is not a CyTubeConnection.
        """
        if isinstance(self.connection, CyTubeConnection):
            return self.connection.socket
        return None
    
    @property
    def response_timeout(self):
        """Response timeout for CyTube operations (backward compatibility)."""
        if isinstance(self.connection, CyTubeConnection):
            return self.connection.response_timeout
        return 0.1  # Default fallback

    def _on_rank(self, _, data):
        self.user.rank = data

    def _on_setMotd(self, _, data):
        self.channel.motd = data

    def _on_channelCSSJS(self, _, data):
        self.channel.css = data.get('css', '')
        self.channel.js = data.get('js', '')

    def _on_channelOpts(self, _, data):
        self.channel.options = data

    def _on_setPermissions(self, _, data):
        self.channel.permissions = data

    def _on_emoteList(self, _, data):
        self.channel.emotes = data

    def _on_drinkCount(self, _, data):
        self.channel.drink_count = data

    async def _on_usercount(self, _, data):
        self.channel.userlist.count = data

        # Update high water mark for connected count when it changes
        user_count = len(self.channel.userlist)
        connected_count = data
        
        # Publish via NATS (REQUIRED)
        await self.nats.publish('rosey.db.stats.high_water', json.dumps({
            'chat_count': user_count,
            'connected_count': connected_count
        }).encode())
        self.logger.debug(f"[NATS] Published high_water: {user_count}/{connected_count}")

    @staticmethod
    def _on_needPassword(_, data):
        if data:
            raise LoginError('invalid channel password')

    def _on_noflood(self, _, data):
        self.logger.error('noflood: %r', data)

    def _on_errorMsg(self, _, data):
        self.logger.error('error: %r', data)

    def _on_queueFail(self, _, data):
        self.logger.error('playlist error: %r', data)

    @staticmethod
    def _on_kick(_, data):
        raise Kicked(data)

    def _add_user(self, data):
        """Add user from normalized or platform-specific data.
        
        Accepts both normalized format (username, rank, is_afk, is_moderator)
        and CyTube format (name, rank, afk) for backward compatibility.
        
        Args:
            data: User data dict with either 'username' or 'name' field
        """
        # Support both normalized 'username' and CyTube 'name'
        username = data.get('username', data.get('name', ''))
        
        # Create User with basic fields that __init__ accepts
        user_dict = {
            'name': username,
            'rank': data.get('rank', 0),
            'meta': data.get('meta', {})
        }
        
        if username == self.user.name:
            self.user.update(**user_dict)
            # Set afk attribute directly (not in __init__)
            self.user.afk = data.get('is_afk', data.get('afk', False))
            self.channel.userlist.add(self.user)
        else:
            new_user = User(**user_dict)
            # Set afk attribute directly (not in __init__)
            new_user.afk = data.get('is_afk', data.get('afk', False))
            self.channel.userlist.add(new_user)

    def _on_user_list(self, _, data):
        """Handle normalized user_list event.
        
        Uses normalized 'users' field which contains array of user objects
        with platform-agnostic structure (username, rank, is_moderator, etc).
        
        ✅ NORMALIZATION COMPLETE (Sortie 2): Uses normalized 'users' array
        """
        self.channel.userlist.clear()
        
        # ✅ Use normalized 'users' array (Sortie 1 provides full objects)
        users_data = data.get('users', [])
        
        for user in users_data:
            # user is now guaranteed to be a dict with normalized fields
            self._add_user(user)
        
        self.logger.info('userlist: %s users', len(self.channel.userlist))

    async def _on_user_join(self, _, data):
        """Handle normalized user_join event.
        
        Uses normalized 'user_data' field which contains full user object
        with platform-agnostic structure.
        
        ✅ NORMALIZATION COMPLETE (Sortie 2): Uses normalized 'user_data' field
        """
        # ✅ Use normalized 'user_data' field (Sortie 1 provides full object)
        user_data = data.get('user_data', {})
        username = data.get('user', user_data.get('username', ''))
        
        if user_data:
            self._add_user(user_data)
            self.logger.info('User joined: %s (rank=%s)', 
                           username, user_data.get('rank', 0))
        else:
            self.logger.warning('User join without user_data: %s', username)

        # Track user join via NATS (REQUIRED)
        if username:
            # Publish via NATS
            await self.nats.publish('rosey.db.user.joined', json.dumps({
                'username': username
            }).encode())
            self.logger.debug(f"[NATS] Published user_joined: {username}")
            
            # Update high water mark
            user_count = len(self.channel.userlist)
            connected_count = self.channel.userlist.count
            await self.nats.publish('rosey.db.stats.high_water', json.dumps({
                'chat_count': user_count,
                'connected_count': connected_count
            }).encode())

    async def _on_user_leave(self, _, data):
        """Handle normalized user_leave event.
        
        Optionally uses 'user_data' field if available for enhanced logging.
        
        ✅ NORMALIZATION COMPLETE (Sortie 2): Uses normalized 'user' field,
        optionally 'user_data' for enhanced logging
        """
        # ✅ Use normalized 'user' field (always present)
        username = data.get('user', '')
        user_data = data.get('user_data', None)  # May be None

        # Track user leave via NATS or database
        if username:
            # Publish via NATS
            await self.nats.publish('rosey.db.user.left', json.dumps({
                'username': username
            }).encode())
            self.logger.debug(f"[NATS] Published user_left: {username}")
        try:
            del self.channel.userlist[username]
            
            # Enhanced logging if user_data available
            if user_data:
                rank = user_data.get('rank', 0)
                was_mod = user_data.get('is_moderator', False)
                self.logger.info('User left: %s (rank=%s, mod=%s)', username, rank, was_mod)
            else:
                self.logger.info('User left: %s', username)
        except KeyError:
            self.logger.error('userLeave: %s not found', username)

    def _on_setUserMeta(self, _, data):
        # Check if user exists before updating metadata
        user_name = data.get('name', '')
        # Ignore blank usernames (server sometimes sends these)
        if not user_name:
            return
        if user_name in self.channel.userlist:
            self.channel.userlist[user_name].meta = data['meta']
        else:
            self.logger.warning(
                'setUserMeta: user %s not in userlist yet', user_name)

    def _on_setUserRank(self, _, data):
        # Check if user exists before updating rank
        user_name = data.get('name', '')
        # Ignore blank usernames (server sometimes sends these)
        if not user_name:
            return
        if user_name in self.channel.userlist:
            self.channel.userlist[user_name].rank = data['rank']
        else:
            self.logger.warning(
                'setUserRank: user %s not in userlist yet', user_name)

    def _on_setAFK(self, _, data):
        # Check if user exists before updating AFK status
        user_name = data.get('name', '')
        # Ignore blank usernames (server sometimes sends these)
        if not user_name:
            return
        if user_name in self.channel.userlist:
            self.channel.userlist[user_name].afk = data['afk']
        else:
            self.logger.warning(
                'setAFK: user %s not in userlist yet', user_name)

    def _on_setLeader(self, _, data):
        self.channel.userlist.leader = data
        self.logger.info('leader %r', self.channel.userlist.leader)

    def _on_setPlaylistMeta(self, _, data):
        self.channel.playlist.time = data.get('rawTime', 0)

    def _on_mediaUpdate(self, _, data):
        self.channel.playlist.paused = data.get('paused', True)
        self.channel.playlist.current_time = data.get('currentTime', 0)

    def _on_voteskip(self, _, data):
        self.channel.voteskip_count = data.get('count', 0)
        self.channel.voteskip_need = data.get('need', 0)
        self.logger.info(
            'voteskip %s / %s',
            self.channel.voteskip_count,
            self.channel.voteskip_need
        )

    def _on_setCurrent(self, _, data):
        self.channel.playlist.current = data
        self.logger.info('setCurrent %s', self.channel.playlist.current)

    def _on_queue(self, _, data):
        self.channel.playlist.add(data['after'], data['item'])
        self.logger.info('queue %s', self.channel.playlist.queue)

    def _on_delete(self, _, data):
        self.channel.playlist.remove(data['uid'])
        self.logger.info('delete %s', self.channel.playlist.queue)

    def _on_setTemp(self, _, data):
        self.channel.playlist.get(data['uid']).temp = data['temp']

    def _on_moveVideo(self, _, data):
        self.channel.playlist.move(data['from'], data['after'])
        self.logger.info('move %s', self.channel.playlist.queue)

    def _on_playlist(self, _, data):
        self.channel.playlist.clear()
        for item in data:
            self.channel.playlist.add(None, item)
        self.logger.info('playlist %s', self.channel.playlist.queue)

    def _on_setPlaylistLocked(self, _, data):
        self.channel.playlist.locked = data
        self.logger.info('playlist locked %s', data)

    async def _on_message(self, _, data):
        """Handle normalized message event."""
        # TODO: NORMALIZATION - This is correct pattern, all handlers should follow this
        # Use normalized fields (user, content) - no platform_data access needed
        username = data.get('user')
        msg = data.get('content', '')
        
        if username:
            # Publish via NATS
            await self.nats.publish('rosey.db.message.log', json.dumps({
                'username': username,
                'message': msg
            }).encode())
            self.logger.debug(f"[NATS] Published message_log: {username}")
    async def _log_user_counts_periodically(self):
        """Background task to periodically log user counts for graphing

        Logs user counts every 5 minutes to build historical data
        """
        try:
            while True:
                await asyncio.sleep(300)  # 5 minutes

                if self.channel and self.channel.userlist:
                    chat_users = len(self.channel.userlist)
                    connected_users = len(self.channel.userlist)  # Same as chat_users for dict-based userlist

                    try:
                        # Publish via NATS
                        await self.nats.publish('rosey.db.stats.user_count', json.dumps({
                            'chat_count': chat_users,
                            'connected_count': connected_users
                        }).encode())
                        self.logger.debug(
                            '[NATS] Published user_count: %d chat, %d connected',
                            chat_users, connected_users
                        )
                    except Exception as e:
                        self.logger.error('Failed to log user counts: %s', e)
        except asyncio.CancelledError:
            self.logger.debug('User count logging task cancelled')

    async def _update_current_status_periodically(self):
        """Background task to update current status for web display

        Updates every 10 seconds with current bot/channel state
        """
        try:
            while True:
                await asyncio.sleep(10)  # 10 seconds

                if self.channel:
                    try:
                        status = {
                            'bot_name': self.user.name,
                            'bot_rank': self.user.rank,
                            'bot_afk': 1 if self.user.afk else 0,
                            'channel_name': self.channel.name,
                            'current_chat_users': len(self.channel.userlist),
                            'current_connected_users': (
                                self.channel.userlist.count or
                                len(self.channel.userlist)
                            ),
                            'bot_start_time': int(self.start_time),
                            'bot_connected': 1 if self.connection.is_connected else 0
                        }

                        # Add playlist info if available
                        if self.channel.playlist:
                            status['playlist_items'] = len(
                                self.channel.playlist.queue)
                            if self.channel.playlist.current:
                                status['current_media_title'] = (
                                    self.channel.playlist.current.title)
                                status['current_media_duration'] = (
                                    self.channel.playlist.current.duration)

                        # Publish via NATS
                        await self.nats.publish('rosey.db.status.update', json.dumps({
                            'status_data': status
                        }).encode())
                        self.logger.debug('[NATS] Published status_update')
                    except Exception as e:
                        self.logger.error('Failed to update status: %s', e)
        except asyncio.CancelledError:
            self.logger.debug('Status update task cancelled')

    async def _process_outbound_messages_periodically(self):
        """Background task to send outbound messages queued by web UI.

        Implements gentle retry logic with exponential backoff:
        - Permanent errors (permission/muted/flood) stop retries immediately
        - Transient errors (network issues) retry with increasing delays
        - Max 3 retry attempts before giving up
        """
        try:
            while True:
                await asyncio.sleep(2)  # Poll every 2 seconds

                # Check if bot is connected and ready
                if not self.nats:
                    continue
                if not self.connection.is_connected:
                    self.logger.debug(
                        'Outbound processor waiting for socket connection'
                    )
                    continue
                if not self.channel.permissions:
                    self.logger.debug(
                        'Outbound processor waiting for channel '
                        'permissions to load'
                    )
                    continue

                try:
                    # Fetch messages ready for sending (respects retry backoff)
                    messages = []
                    
                    # Query via NATS request/reply
                    try:
                        response = await self.nats.request(
                            'rosey.db.messages.outbound.get',
                            json.dumps({'limit': 20, 'max_retries': 3}).encode(),
                            timeout=2.0
                        )
                        messages = json.loads(response.data.decode())
                        self.logger.debug(f"[NATS] Queried outbound messages: {len(messages)} found")
                    except asyncio.TimeoutError:
                        self.logger.warning("[NATS] Timeout querying outbound messages")
                        messages = []
                    except Exception as e:
                        self.logger.error(f"[NATS] Error querying outbound messages: {e}")
                        messages = []
                    if messages:
                        self.logger.debug(
                            'Processing %d queued outbound message(s)',
                            len(messages)
                        )

                    for m in messages:
                        mid = m['id']
                        text = m['message']
                        retry_count = m.get('retry_count', 0)

                        try:
                            await self.chat(text)
                            
                            # Mark as sent via NATS or database
                            await self.nats.publish('rosey.db.messages.outbound.mark_sent', json.dumps({
                                'message_id': mid
                            }).encode())
                            if retry_count > 0:
                                self.logger.info(
                                    'Sent outbound id=%s after %d retries',
                                    mid, retry_count
                                )
                            else:
                                self.logger.info('Sent outbound id=%s', mid)

                        except Exception as send_exc:
                            from .error import (
                                ChannelPermissionError,
                                ChannelError
                            )

                            error_msg = str(send_exc)

                            # Classify error as permanent or transient
                            if isinstance(send_exc, (
                                    ChannelPermissionError,
                                    ChannelError)):
                                # Permanent: permissions, muted, flood control
                                # For now, we can't mark as failed via NATS
                                # (DatabaseService doesn't have mark_failed handler yet)
                                # TODO: Add mark_failed handler to DatabaseService
                                self.logger.error(
                                    'Permanent failure for outbound id=%s: %s',
                                    mid, error_msg
                                )
                            else:
                                # Transient: network, timeout, etc - will retry
                                # TODO: Add mark_failed handler to DatabaseService
                                self.logger.warning(
                                    'Transient failure for outbound id=%s '
                                    '(retry %d): %s',
                                    mid, retry_count + 1, error_msg
                                )

                except Exception as e:
                    self.logger.error(
                        'Error processing outbound messages: %s', e
                    )
        except asyncio.CancelledError:
            self.logger.debug('Outbound processing task cancelled')

    async def _perform_maintenance_periodically(self):
        """Background task for periodic database maintenance.

        Runs once per day (at startup and then every 24 hours) to:
        - Clean up old records (history, outbound messages, tokens)
        - VACUUM database to reclaim space
        - Update query planner statistics
        """
        try:
            while True:
                # Run immediately on startup, then every 24 hours
                # TODO: Implement maintenance via NATS/DatabaseService
                try:
                    self.logger.info('Database maintenance check (NATS mode - TODO)')
                    # Maintenance would be handled by DatabaseService
                    # Could publish to 'db.maintenance' subject
                except Exception as e:
                    self.logger.error(
                        'Database maintenance check failed: %s', e
                    )

                # Wait 24 hours before next maintenance
                await asyncio.sleep(86400)

        except asyncio.CancelledError:
            self.logger.debug('Maintenance task cancelled')

    async def run(self):
        """Main event loop.
        """
        import time
        try:
            # Start background tasks for logging and status updates (via NATS)
            self._history_task = asyncio.create_task(
                self._log_user_counts_periodically()
            )
            self._status_task = asyncio.create_task(
                self._update_current_status_periodically()
            )
            self._outbound_task = asyncio.create_task(
                self._process_outbound_messages_periodically()
            )
            self._maintenance_task = asyncio.create_task(
                self._perform_maintenance_periodically()
            )

            while True:
                try:
                    if not self.connection.is_connected:
                        self.logger.info('connecting')
                        await self.connection.connect()
                        self.connect_time = time.time()  # Record connection time
                    
                    async for ev, data in self.connection.recv_events():
                        await self.trigger(ev, data)
                        
                except (ConnError, Exception) as ex:
                    self.logger.error('connection error: %r', ex, exc_info=True)
                    try:
                        await self.connection.disconnect()
                    except Exception:
                        pass
                    
                    if self.restart_delay is None or self.restart_delay <= 0:
                        break
                    
                    self.logger.error('restarting in %s seconds', self.restart_delay)
                    await asyncio.sleep(self.restart_delay)
                    await self.connection.reconnect()
                    
        except asyncio.CancelledError:
            self.logger.info('cancelled')
        finally:
            # Cancel background tasks
            if self._history_task:
                self._history_task.cancel()
                try:
                    await self._history_task
                except asyncio.CancelledError:
                    pass

            if self._status_task:
                self._status_task.cancel()
                try:
                    await self._status_task
                except asyncio.CancelledError:
                    pass

            if self._outbound_task:
                self._outbound_task.cancel()
                try:
                    await self._outbound_task
                except asyncio.CancelledError:
                    pass

            if self._maintenance_task:
                self._maintenance_task.cancel()
                try:
                    await self._maintenance_task
                except asyncio.CancelledError:
                    pass

            try:
                await self.connection.disconnect()
            except Exception as ex:
                self.logger.error('disconnect error: %r', ex)

    def on(self, event, *handlers):
        """Add event handlers.

        Parameters
        ----------
        event : `str`
            Event name.
        handlers : `list` of `function`
            Event handlers.
        """
        ev_handlers = self.handlers[event]
        for handler in handlers:
            if handler not in ev_handlers:
                ev_handlers.append(handler)
                self.logger.info('on: %s %s', event, handler)
            else:
                self.logger.warning('on: handler exists: %s %s', event, handler)
        return self

    def off(self, event, *handlers):
        """Remove event handlers.

        Parameters
        ----------
        event : `str`
            Event name.
        handlers : `list` of `function`
            Event handlers.
        """
        ev_handlers = self.handlers[event]
        for handler in handlers:
            try:
                ev_handlers.remove(handler)
                self.logger.info('off: %s %s', event, handler)
            except ValueError:
                self.logger.warning(
                    'off: handler not found: %s %s',
                    event, handler
                )
        return self

    async def trigger(self, event, data):
        """Trigger an event.

        Parameters
        ----------
        event : `str`
            Event name.
        data : `object`
            Event data.

        Raises
        ------
        `cytube_bot.error.LoginError`
        `cytube_bot.error.Kicked`
        """
        level = self.EVENT_LOG_LEVEL.get(event, self.EVENT_LOG_LEVEL_DEFAULT)
        self.logger.log(level, 'trigger: %s %s', event, data)
        try:
            for handler in self.handlers[event]:
                if asyncio.iscoroutinefunction(handler):
                    stop = await handler(event, data)
                else:
                    stop = handler(event, data)
                if stop:
                    break
        except (asyncio.CancelledError, LoginError, Kicked):
            raise
        except Exception as ex:  # pylint: disable=broad-except
            self.logger.error('trigger %s %s: %r', event, data, ex)
            if event != 'error':
                await self.trigger('error', {
                    'event': event,
                    'data': data,
                    'error': ex
                })

    async def chat(self, msg, meta=None):
        """Send a chat message.

        Parameters
        ----------
        msg : `str`
        meta : `None` or `dict`, optional

        Returns
        -------
        `dict`
            Message data.

        Raises
        ------
        cytube_bot.error.ChannelError
        cytube_bot.error.ChannelPermissionError
        """
        self.logger.info('chat %s', msg)
        self.channel.check_permission('chat', self.user)

        if self.user.muted or self.user.smuted:
            raise ChannelPermissionError('muted')

        try:
            await self.connection.send_message(msg, meta=meta)
            # Return dict for compatibility
            return {'msg': msg, 'meta': meta if meta else {}}
        except NotConnectedError:
            self.logger.error('chat: not connected')
            raise ChannelError('not connected')
        except Exception as ex:
            self.logger.error('chat: error: %r', ex)
            raise ChannelError(f'could not send chat message: {ex}')

    async def pm(self, to, msg, meta=None):
        """Send a private chat message.

        Parameters
        ----------
        to : `str`
        msg : `str`
        meta : `None` or `dict`, optional

        Returns
        -------
        `dict`
            Message data.

        Raises
        ------
        cytube_bot.error.ChannelPermissionError
        cytube_bot.error.ChannelError
        """
        self.logger.info('pm %s %s', to, msg)
        self.channel.check_permission('chat', self.user)

        if self.user.muted or self.user.smuted:
            raise ChannelPermissionError('muted')

        try:
            await self.connection.send_pm(to, msg)
            # Return dict for compatibility
            return {'to': to, 'msg': msg, 'meta': meta if meta else {}}
        except NotConnectedError:
            self.logger.error('pm: %s: not connected', to)
            raise ChannelError('not connected')
        except Exception as ex:
            self.logger.error('pm: %s: error: %r', to, ex)
            raise ChannelError(f'could not send private message: {ex}')

    async def set_afk(self, value=True):
        """Set bot AFK.

        Parameters
        ----------
        value : `bool`, optional

        Raises
        ------
        cytube_bot.error.ChannelPermissionError
        """
        if self.user.afk != value:
            await self.connection.send_message('/afk')

    async def clear_chat(self):
        """Clear chat.

        Raises
        ------
        cytube_bot.error.ChannelPermissionError
        """
        self.channel.check_permission('chatclear', self.user)
        await self.connection.send_message('/clear')

    async def kick(self, user, reason=''):
        """Kick a user.

        Parameters
        ----------
        user : `str` or `cytube_bot.user.User`
        reason : `str`, optional

        Raises
        ------
        cytube_bot.error.ChannelError
        cytube_bot.error.ChannelPermissionError
        ValueError
        """
        def match_kick_response(event, data):
            if event == 'errorMsg':
                return True
            if event == 'userLeave':
                return data.get('name') == user
            return False

        self.channel.check_permission('kick', self.user)
        if not isinstance(user, User):
            user = self.channel.userlist.get(user)
        if self.user.rank <= user.rank:
            raise ChannelPermissionError(
                'You do not have permission to kick ' + user.name
            )
        res = await self.socket.emit(
            'chatMsg',
            {
                'msg': '/kick %s %s' % (user.name, reason),
                'meta': {},
            },
            match_kick_response,
            self.response_timeout
        )
        if res is None:
            raise ChannelError('kick response timeout')
        if res[0] == 'errorMsg':
            raise ChannelPermissionError(res[1].get('msg', '<no message>'))

    async def add_media(self, link, append=True, temp=True):
        """Add media link to playlist.

        Parameters
        ----------
        link : `str` or `cytube_bot.media_link.MediaLink`
            Media link.
        append : `bool`, optional
            `True` - append, `False` - insert after current item.
        temp : `bool`, optional
            `True` to add temporary item.

        Returns
        -------
        `dict`
            Playlist item data.

        Raises
        ------
        cytube_bot.error.ChannelPermissionError
        cytube_bot.error.ChannelError
        ValueError
        """

        def match_add_media_response(event, data):
            if event == 'queueFail':
                return True
            if event == 'queue':
                item = data.get('item', {})
                media = item.get('media', {})
                return (
                    item.get('queueby') == self.user.name
                    and media.get('type') == link.type
                    and media.get('id') == link.id
                )
            return False

        action = 'playlist' if self.channel.playlist.locked else 'oplaylist'
        self.logger.info('add media %s', link)
        self.channel.check_permission(action + 'add', self.user)
        if not append:
            self.channel.check_permission(action + 'next', self.user)
        if not temp:
            self.channel.check_permission('addnontemp', self.user)

        if not isinstance(link, MediaLink):
            link = MediaLink.from_url(link)

        res = await self.socket.emit(
            'queue',
            {
                'type': link.type,
                'id': link.id,
                'pos': 'end' if append else 'next',
                'temp': temp
            },
            match_add_media_response,
            self.response_timeout
        )

        if res is None:
            raise ChannelError('add media response timeout')
        if res[0] == 'queueFail':
            self.logger.info('queueFail %r', res)
            raise ChannelError(res[1].get('msg', '<no message>'))
        return res[1]

    async def remove_media(self, item):
        """Remove playlist item.

        Parameters
        ----------
        item: `int` or `cytube_bot.playlist.PlaylistItem`
            Item to remove.

        Raises
        ------
        cytube_bot.error.ChannelPermissionError
        ValueError
        """

        def match_remove_media_response(event, data):
            if event == 'delete':
                return data.get('uid') == item.uid
            return False

        if self.channel.playlist.locked:
            action = 'playlistdelete'
        else:
            action = 'oplaylistdelete'
        self.channel.check_permission(action, self.user)
        if not isinstance(item, PlaylistItem):
            item = self.channel.playlist.get(item)
        res = await self.socket.emit(
            'delete',
            item.uid,
            match_remove_media_response,
            self.response_timeout
        )
        if res is None:
            raise ChannelError('remove media response timeout')

    async def move_media(self, item, after):
        """Move a playlist item.

        Parameters
        ----------
        item: `int` or `cytube_bot.playlist.PlaylistItem`
        after: `int` or `cytube_bot.playlist.PlaylistItem`

        Raises
        ------
        cytube_bot.error.ChannelError
        cytube_bot.error.ChannelPermissionError
        ValueError
        """
        def match_remove_media_response(event, data):
            if event == 'moveVideo':
                return (
                    data.get('from') == item.uid
                    and data.get('after') == after.uid
                )
            return False

        if self.channel.playlist.locked:
            action = 'playlistmove'
        else:
            action = 'oplaylistmove'
        self.channel.check_permission(action, self.user)

        if not isinstance(item, PlaylistItem):
            item = self.channel.playlist.get(item)
        if not isinstance(after, PlaylistItem):
            after = self.channel.playlist.get(after)

        res = await self.socket.emit(
            'moveMedia',
            {
                'from': item.uid,
                'after': after.uid
            },
            match_remove_media_response,
            self.response_timeout
        )
        if res is None:
            raise ChannelError('move media response timeout')

    async def set_current_media(self, item):
        """Set current playlist item.

        Parameters
        ----------
        item: `int` or `cytube_bot.playlist.PlaylistItem`

        Raises
        ------
        cytube_bot.error.ChannelError
        cytube_bot.error.ChannelPermissionError
        ValueError
        """
        def match_set_current_response(event, data):
            if event == 'setCurrent':
                return data == item.uid
            return False

        if self.channel.playlist.locked:
            action = 'playlistjump'
        else:
            action = 'oplaylistjump'
        self.channel.check_permission(action, self.user)
        if not isinstance(item, PlaylistItem):
            item = self.channel.playlist.get(item)
        res = await self.socket.emit(
            'jumpTo',
            item.uid,
            match_set_current_response,
            self.response_timeout
        )
        if res is None:
            raise ChannelError('set current response timeout')

    async def set_leader(self, user):
        """Set leader.

        Parameters
        ----------
        user: `None` or `str` or `cytube_bot.user.User`

        Raises
        ------
        cytube_bot.error.ChannelPermissionError
        cytube_bot.error.ChannelError
        ValueError
        """
        def match_set_leader_response(event, data):
            if event == 'setLeader':
                if user is None:
                    return data == ''
                else:
                    return data == user.name
            return False

        self.channel.check_permission('leaderctl', self.user)
        if user is not None and not isinstance(user, User):
            user = self.channel.userlist.get(user)
        res = await self.socket.emit(
            'assignLeader',
            {'name': user.name if user is not None else ''},
            match_set_leader_response,
            self.response_timeout
        )
        if res is None:
            raise ChannelError('set leader response timeout')

    async def remove_leader(self):
        """Remove leader."""
        await self.set_leader(None)

    async def pause(self):
        """Pause current media.

        Raises
        ------
        cytube_bot.error.ChannelPermissionError
        """
        if self.channel.userlist.leader is not self.user:
            raise ChannelPermissionError('can not pause: not a leader')

        if self.channel.playlist.current is None:
            return

        await self.socket.emit('mediaUpdate', {
            'currentTime': self.channel.playlist.current_time,
            'paused': True,
            'id': self.channel.playlist.current.link.id,
            'type': self.channel.playlist.current.link.type
        })
