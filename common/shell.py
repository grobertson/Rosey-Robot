#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PM command interface for bot control via moderator private messages"""
import asyncio
import json
import logging
import time
from datetime import datetime

from lib import MediaLink


class Shell:
    '''PM command interface for bot control.

    Handles moderator commands sent via private messages.
    TCP/telnet server functionality has been removed - use REST API instead.
    '''
    logger = logging.getLogger(__name__)

    @staticmethod
    def format_duration(seconds):
        """Format seconds into human-readable duration"""
        if seconds < 0:
            return "Unknown"

        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")

        return ' '.join(parts)

    HELP_TEXT = """
Bot Commands:
───────────────────────────────
Info:
 help - Show commands
 info - Bot & channel
 status - Connection
 stats - Database stats

Users:
 users - List all
 user <name> - User info
 afk [on|off] - Set AFK

Chat:
 say <msg> - Chat msg
 pm <u> <msg> - Private msg

Playlist:
 playlist [n] - Show queue
 current - Now playing
 add <url> [t] - Add video
 remove <#> - Delete item
 move <#> <#> - Reorder
 jump <#> - Jump to
 next - Skip video

Control:
 pause - Pause vid
 kick <u> [r] - Kick user
 voteskip - Skip vote

Examples:
 say Hello everyone!
 add youtu.be/xyz yes
 playlist 5
 kick Bob Spamming
───────────────────────────────
"""

    def __init__(self, addr, bot, loop=None):
        '''Initialize the PM command handler

        Args:
            addr: Ignored (kept for backward compatibility with existing code)
            bot: lib.Bot instance to interact with
            loop: Ignored (kept for backward compatibility)
        '''
        self.bot = bot if addr is not None else None
        if addr is None:
            self.logger.info('PM command interface disabled')

    async def handle_pm_command(self, event, data):  # noqa: C901 (complex PM routing)
        """Handle commands sent via PM from moderators

        Args:
            event: Event name ('pm')
            data: PM data containing username, msg, etc.

        Returns:
            None - responses are sent back via PM
        """
        self.logger.debug('handle_pm_command called: event=%s, data=%s', event, data)

        # TODO: NORMALIZATION - Shell should only use normalized fields (user, content)
        # Platform-specific access to platform_data should be removed once normalization is complete
        # Extract data from PM - check both normalized and platform_data locations
        platform_data = data.get('platform_data', {})
        username = data.get('user', platform_data.get('username', ''))
        message = data.get('content', platform_data.get('msg', '')).strip()

        # Ignore empty messages
        if not message:
            return

        # Ignore PMs from ourselves (prevents infinite error loops)
        bot = self.bot
        if username == bot.user.name:
            self.logger.debug('Ignoring PM from self')
            return

        # Get the user object if available
        if bot.channel and username in bot.channel.userlist:
            user = bot.channel.userlist[username]

            # Check if user is a moderator (rank 2.0+)
            if user.rank < 2.0:
                self.logger.info('PM command from non-moderator %s: %s',
                               username, message)
                # Don't respond to non-moderators to avoid spam
                return
        else:
            # User not in userlist - this can happen if they joined before bot
            # or if there's a sync issue. Fail closed (reject) to prevent
            # potential privilege escalation via authorization bypass
            self.logger.warning('PM from user not in userlist: %s (rejecting command for security)', username)
            return

        self.logger.info('PM command from %s: %s', username, message)

        # Parse command for logging
        command_parts = message.split(None, 1)
        command_name = command_parts[0].lower() if command_parts else 'unknown'
        command_args = command_parts[1] if len(command_parts) > 1 else ''

        # Log PM command via NATS (fire-and-forget audit trail)
        if bot.nats and bot.nats.is_connected:
            try:
                await bot.nats.publish(
                    'rosey.db.action.pm_command',
                    json.dumps({
                        'timestamp': time.time(),
                        'username': username,
                        'command': command_name,
                        'args': command_args,  # Log full args for audit trail
                        'result': 'pending',
                        'error': None
                    }).encode()
                )
            except Exception as e:
                # Don't fail command if logging fails (fire-and-forget)
                self.logger.debug(f"PM command logging failed (non-fatal): {e}")

        # Process the command
        command_result = 'success'
        command_error = None
        try:
            result = await self.handle_command(message, bot)

            # Send response back via PM
            if result:
                # Split long responses into multiple messages
                max_length = 500
                lines = result.split('\n')
                current_chunk = []
                current_length = 0

                for line in lines:
                    line_length = len(line) + 1  # +1 for newline
                    if current_length + line_length > max_length and current_chunk:
                        # Send current chunk
                        response = '\n'.join(current_chunk)
                        await bot.pm(username, response)
                        current_chunk = [line]
                        current_length = line_length
                    else:
                        current_chunk.append(line)
                        current_length += line_length

                # Send remaining chunk
                if current_chunk:
                    response = '\n'.join(current_chunk)
                    await bot.pm(username, response)

        except Exception as e:
            command_result = 'error'
            command_error = str(e)
            self.logger.error('Error processing PM command: %s', e,
                            exc_info=True)
            try:
                await bot.pm(username, f"Error: {e}")
            except Exception:
                pass  # Don't fail if we can't send error message

        finally:
            # Log final result (success or error)
            if bot.nats and bot.nats.is_connected:
                try:
                    await bot.nats.publish(
                        'rosey.db.action.pm_command',
                        json.dumps({
                            'timestamp': time.time(),
                            'username': username,
                            'command': command_name,
                            'args': command_args,  # Log full args
                            'result': command_result,
                            'error': command_error
                        }).encode()
                    )
                except Exception as e:
                    self.logger.debug(f"PM result logging failed (non-fatal): {e}")

    async def handle_command(self, cmd, bot):  # noqa: C901 (complex function)
        """Handle bot control commands

        Args:
            cmd: The command string to process
            bot: The bot instance to control

        Returns:
            String response
        """
        # Parse command and arguments
        parts = cmd.strip().split(None, 1)
        if not parts:
            return None

        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        try:
            # === Connection & Info Commands ===
            if command == 'help':
                return self.HELP_TEXT

            elif command == 'info':
                return await self.cmd_info(bot)

            elif command == 'status':
                return await self.cmd_status(bot)

            elif command == 'stats':
                return await self.cmd_stats(bot)

            # === User Management ===
            elif command == 'users':
                return await self.cmd_users(bot)

            elif command == 'user':
                return await self.cmd_user(bot, args)

            elif command == 'afk':
                return await self.cmd_afk(bot, args)

            # === Chat Commands ===
            elif command == 'say':
                return await self.cmd_say(bot, args)

            elif command == 'pm':
                return await self.cmd_pm(bot, args)

            elif command == 'clear':
                return await self.cmd_clear(bot)

            # === Playlist Management ===
            elif command == 'playlist':
                return await self.cmd_playlist(bot, args)

            elif command == 'current':
                return await self.cmd_current(bot)

            elif command == 'add':
                return await self.cmd_add(bot, args)

            elif command == 'remove':
                return await self.cmd_remove(bot, args)

            elif command == 'move':
                return await self.cmd_move(bot, args)

            elif command == 'jump':
                return await self.cmd_jump(bot, args)

            elif command == 'next':
                return await self.cmd_next(bot)

            # === Channel Control ===
            elif command == 'pause':
                return await self.cmd_pause(bot)

            elif command == 'kick':
                return await self.cmd_kick(bot, args)

            elif command == 'voteskip':
                return await self.cmd_voteskip(bot)

            else:
                return f"Unknown command: {command}\nType 'help' for available commands"

        except Exception as e:
            self.logger.error('Command error: %s', e, exc_info=True)
            return f"Error: {e}"

    # === Command Implementations ===

    async def cmd_info(self, bot):
        """Show bot and channel information"""
        info = []
        info.append(f"Bot: {bot.user.name}")
        info.append(f"Rank: {bot.user.rank}")
        info.append(f"AFK: {'Yes' if bot.user.afk else 'No'}")
        if bot.channel:
            info.append(f"Channel: {bot.channel.name}")

            # Show both chat users and total connected viewers
            chat_users = len(bot.channel.userlist)
            total_viewers = bot.channel.userlist.count
            if total_viewers and total_viewers != chat_users:
                info.append(f"Users: {chat_users} in chat, "
                          f"{total_viewers} connected")
            else:
                info.append(f"Users: {chat_users}")

            if bot.channel.playlist:
                total = len(bot.channel.playlist.queue)
                info.append(f"Playlist: {total} items")
                # Calculate total playlist duration from queue items
                total_time = sum(item.duration for item in bot.channel.playlist.queue)
                if total_time > 0:
                    duration = self.format_duration(total_time)
                    info.append(f"Duration: {duration}")
                if bot.channel.playlist.current:
                    info.append(f"Now playing: "
                               f"{bot.channel.playlist.current.title}")
        return '\n'.join(info)

    async def cmd_status(self, bot):
        """Show connection status"""
        import time
        status = []

        # Bot uptime
        if hasattr(bot, 'start_time') and bot.start_time:
            uptime = time.time() - bot.start_time
            status.append(f"Uptime: {self.format_duration(uptime)}")

        # Connection status and duration
        status.append(f"Connected: {'Yes' if bot.socket else 'No'}")
        if bot.socket:
            status.append(f"Server: {bot.server}")
            if hasattr(bot, 'connect_time') and bot.connect_time:
                conn_duration = time.time() - bot.connect_time
                status.append(f"Conn time: {self.format_duration(conn_duration)}")

        if bot.channel:
            status.append(f"Channel: {bot.channel.name}")
            if bot.channel.userlist.leader:
                status.append(f"Leader: {bot.channel.userlist.leader.name}")
            if bot.channel.playlist:
                paused = bot.channel.playlist.paused
                status.append(f"Playback: {'Paused' if paused else 'Playing'}")
        return '\n'.join(status)

    async def cmd_stats(self, bot):
        """Show database statistics via NATS query.
        
        Queries DatabaseService via NATS request/reply for channel statistics
        including high water marks, top chatters, and total users seen.
        
        Returns:
            str: Formatted statistics or error message
        """
        if not bot.nats or not bot.nats.is_connected:
            return "Stats unavailable (NATS not connected)"
        
        try:
            # Request channel stats from DatabaseService
            response = await bot.nats.request(
                'rosey.db.query.channel_stats',
                b'{}',
                timeout=1.0
            )
            
            # Parse response
            stats = json.loads(response.data.decode())
            
            if not stats.get('success', False):
                error = stats.get('error', 'Unknown error')
                return f"Stats error: {error}"
            
            # Format output
            output = []
            output.append("=== Channel Statistics ===")
            
            # High water mark (chat users)
            hwm = stats['high_water_mark']
            if hwm['timestamp']:
                dt = datetime.fromtimestamp(hwm['timestamp'])
                output.append(f"Peak chat users: {hwm['users']} ({dt.strftime('%Y-%m-%d %H:%M')})")
            else:
                output.append(f"Peak chat users: {hwm['users']}")
            
            # High water mark (connected viewers)
            hwm_connected = stats['high_water_connected']
            if hwm_connected['timestamp']:
                dt = datetime.fromtimestamp(hwm_connected['timestamp'])
                output.append(f"Peak connected viewers: {hwm_connected['users']} ({dt.strftime('%Y-%m-%d %H:%M')})")
            else:
                output.append(f"Peak connected viewers: {hwm_connected['users']}")
            
            # Total users
            output.append(f"Total unique users: {stats['total_users_seen']}")
            
            # Top chatters
            top_chatters = stats.get('top_chatters', [])
            if top_chatters:
                output.append("\n=== Top Chatters ===")
                for i, chatter in enumerate(top_chatters[:10], 1):
                    output.append(f"{i}. {chatter['username']}: {chatter['chat_lines']} messages")
            
            return '\n'.join(output)
        
        except asyncio.TimeoutError:
            return "Stats unavailable (DatabaseService timeout - is it running?)"
        
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid stats response: {e}")
            return "Stats error: Invalid response from DatabaseService"
        
        except Exception as e:
            self.logger.error(f"Stats command error: {e}", exc_info=True)
            return f"Stats error: {str(e)}"

    async def cmd_users(self, bot):
        """List all users in channel"""
        if not bot.channel or not bot.channel.userlist:
            return "No users information available"

        users = []
        for user in sorted(bot.channel.userlist.values(),
                          key=lambda u: u.rank, reverse=True):
            flags = []
            if user.afk:
                flags.append("AFK")
            if user.muted:
                flags.append("MUTED")
            if bot.channel.userlist.leader == user:
                flags.append("LEADER")

            flag_str = f" [{', '.join(flags)}]" if flags else ""
            users.append(f"  [{user.rank}] {user.name}{flag_str}")

        return f"Users in channel ({len(users)}):\n" + '\n'.join(users)

    async def cmd_user(self, bot, username):
        """Show detailed info about a user"""
        if not username:
            return "Usage: user <username>"

        if not bot.channel or username not in bot.channel.userlist:
            return f"User '{username}' not found"

        user = bot.channel.userlist[username]
        info = []
        info.append(f"User: {user.name}")
        info.append(f"Rank: {user.rank}")
        info.append(f"AFK: {'Yes' if user.afk else 'No'}")
        info.append(f"Muted: {'Yes' if user.muted else 'No'}")
        if user.ip:
            info.append(f"IP: {user.ip}")
            if user.uncloaked_ip:
                info.append(f"Uncloaked: {user.uncloaked_ip}")
        if user.aliases:
            info.append(f"Aliases: {', '.join(user.aliases)}")
        if bot.channel.userlist.leader == user:
            info.append("Status: LEADER")

        # Query database stats via NATS (if available)
        if bot.nats and bot.nats.is_connected:
            try:
                response = await bot.nats.request(
                    'rosey.db.query.user_stats',
                    json.dumps({'username': username}).encode(),
                    timeout=1.0
                )
                
                stats = json.loads(response.data.decode())
                
                if stats.get('success') and stats.get('found'):
                    info.append("\n--- Database Statistics ---")
                    
                    # Chat messages
                    info.append(f"Chat messages: {stats['total_chat_lines']}")
                    
                    # Time connected (convert seconds to hours/minutes)
                    total_seconds = stats['total_time_connected']
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    info.append(f"Time connected: {hours}h {minutes}m")
                    
                    # First seen
                    first_seen = datetime.fromtimestamp(stats['first_seen'])
                    info.append(f"First seen: {first_seen.strftime('%Y-%m-%d %H:%M')}")
                    
                    # Last seen
                    last_seen = datetime.fromtimestamp(stats['last_seen'])
                    info.append(f"Last seen: {last_seen.strftime('%Y-%m-%d %H:%M')}")
                    
                    # Current session
                    if stats.get('current_session_start'):
                        info.append("Status: Currently connected")
                
                elif stats.get('success') and not stats.get('found'):
                    info.append("\n--- Database Statistics ---")
                    info.append("No database history for this user")
            
            except asyncio.TimeoutError:
                info.append("\n--- Database Statistics ---")
                info.append("Database stats unavailable (timeout)")
            
            except Exception as e:
                self.logger.debug(f"Could not fetch user stats: {e}")
                # Don't show error to user - stats are optional

        return '\n'.join(info)

    async def cmd_afk(self, bot, args):
        """Set bot AFK status"""
        if not args:
            return f"Current AFK status: {'On' if bot.user.afk else 'Off'}"

        args_lower = args.lower()
        if args_lower in ('on', 'yes', 'true', '1'):
            await bot.set_afk(True)
            return "AFK status: On"
        elif args_lower in ('off', 'no', 'false', '0'):
            await bot.set_afk(False)
            return "AFK status: Off"
        else:
            return "Usage: afk [on|off]"

    async def cmd_say(self, bot, message):
        """Send a chat message"""
        if not message:
            return "Usage: say <message>"

        await bot.chat(message)
        return f"Sent: {message}"

    async def cmd_pm(self, bot, args):
        """Send a private message"""
        parts = args.split(None, 1)
        if len(parts) < 2:
            return "Usage: pm <user> <message>"

        username, message = parts
        await bot.pm(username, message)
        return f"PM sent to {username}: {message}"

    async def cmd_clear(self, bot):
        """Clear chat"""
        await bot.clear_chat()
        return "Chat cleared"

    async def cmd_playlist(self, bot, args):
        """Show playlist"""
        if not bot.channel or not bot.channel.playlist:
            return "No playlist information available"

        # Parse optional limit argument
        limit = 10
        if args:
            try:
                limit = int(args)
            except ValueError:
                return "Usage: playlist [number]"

        queue = bot.channel.playlist.queue
        items = []
        for i, item in enumerate(queue[:limit], 1):
            marker = "► " if item == bot.channel.playlist.current else "  "
            duration = self.format_duration(item.duration)
            items.append(f"{marker}{i}. {item.title} ({duration})")

        result = f"Playlist ({len(queue)} items):\n" + '\n'.join(items)
        if len(queue) > limit:
            result += f"\n  ... and {len(queue) - limit} more"

        return result

    async def cmd_current(self, bot):
        """Show currently playing item"""
        if not bot.channel or not bot.channel.playlist:
            return "No playlist information available"

        current = bot.channel.playlist.current
        if not current:
            return "Nothing is currently playing"

        info = []
        info.append(f"Title: {current.title}")
        duration = self.format_duration(current.duration)
        info.append(f"Duration: {duration}")
        info.append(f"Queued by: {current.username}")
        info.append(f"URL: {current.link.url}")
        info.append(f"Temporary: {'Yes' if current.temp else 'No'}")

        paused = bot.channel.playlist.paused
        current_time = bot.channel.playlist.current_time
        info.append(f"Status: {'Paused' if paused else 'Playing'}")
        info.append(f"Position: {current_time}s")

        return '\n'.join(info)

    async def cmd_add(self, bot, args):
        """Add media to playlist"""
        parts = args.split()
        if not parts:
            return "Usage: add <url> [temp]  (temp: yes/no, default=yes)"

        url = parts[0]
        temp = True

        if len(parts) > 1:
            temp_arg = parts[1].lower()
            if temp_arg in ('no', 'false', '0', 'perm'):
                temp = False

        try:
            link = MediaLink.from_url(url)
            await bot.add_media(link, append=True, temp=temp)
            return f"Added: {url} ({'temporary' if temp else 'permanent'})"
        except Exception as e:
            return f"Failed to add media: {e}"

    async def cmd_remove(self, bot, args):
        """Remove item from playlist"""
        if not args:
            return "Usage: remove <position>"

        try:
            pos = int(args)
        except ValueError:
            return "Invalid position number"

        if not bot.channel or not bot.channel.playlist:
            return "No playlist available"

        queue = bot.channel.playlist.queue
        if pos < 1 or pos > len(queue):
            return f"Position must be between 1 and {len(queue)}"

        item = queue[pos - 1]
        await bot.remove_media(item)
        return f"Removed: {item.title}"

    async def cmd_move(self, bot, args):
        """Move playlist item"""
        parts = args.split()
        if len(parts) < 2:
            return "Usage: move <from_pos> <to_pos>"

        try:
            from_pos = int(parts[0])
            to_pos = int(parts[1])
        except ValueError:
            return "Invalid position numbers"

        if not bot.channel or not bot.channel.playlist:
            return "No playlist available"

        queue = bot.channel.playlist.queue
        if from_pos < 1 or from_pos > len(queue):
            return f"From position must be between 1 and {len(queue)}"
        if to_pos < 1 or to_pos > len(queue):
            return f"To position must be between 1 and {len(queue)}"

        from_item = queue[from_pos - 1]
        # After position in CyTube is the item before the target position
        after_item = queue[to_pos - 2] if to_pos > 1 else None

        if after_item:
            await bot.move_media(from_item, after_item)
        else:
            # Move to beginning - no "after" item
            return "Moving to beginning not yet supported"

        return f"Moved {from_item.title} from position {from_pos} to {to_pos}"

    async def cmd_jump(self, bot, args):
        """Jump to playlist item"""
        if not args:
            return "Usage: jump <position>"

        try:
            pos = int(args)
        except ValueError:
            return "Invalid position number"

        if not bot.channel or not bot.channel.playlist:
            return "No playlist available"

        queue = bot.channel.playlist.queue
        if pos < 1 or pos > len(queue):
            return f"Position must be between 1 and {len(queue)}"

        item = queue[pos - 1]
        await bot.set_current_media(item)
        return f"Jumped to: {item.title}"

    async def cmd_next(self, bot):
        """Skip to next item"""
        if not bot.channel or not bot.channel.playlist:
            return "No playlist available"

        current = bot.channel.playlist.current
        if not current:
            return "Nothing is currently playing"

        queue = bot.channel.playlist.queue
        try:
            current_idx = queue.index(current)
            if current_idx + 1 < len(queue):
                next_item = queue[current_idx + 1]
                await bot.set_current_media(next_item)
                return f"Skipped to: {next_item.title}"
            else:
                return "Already at last item"
        except ValueError:
            return "Current item not in queue"

    async def cmd_pause(self, bot):
        """Pause playback"""
        await bot.pause()
        return "Paused"

    async def cmd_kick(self, bot, args):
        """Kick a user"""
        parts = args.split(None, 1)
        if not parts:
            return "Usage: kick <user> [reason]"

        username = parts[0]
        reason = parts[1] if len(parts) > 1 else ""

        await bot.kick(username, reason)
        return f"Kicked {username}" + (f": {reason}" if reason else "")

    async def cmd_voteskip(self, bot):
        """Show voteskip status"""
        if not bot.channel:
            return "No channel information available"

        count = bot.channel.voteskip_count
        need = bot.channel.voteskip_need
        return f"Voteskip: {count}/{need}"

