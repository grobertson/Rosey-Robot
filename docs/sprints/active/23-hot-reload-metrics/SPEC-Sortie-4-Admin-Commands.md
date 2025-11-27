# SPEC: Sortie 4 - Admin Commands

**Sprint:** 23 - Hot-Reload & Metrics Dashboard  
**Sortie:** 4 of 5  
**Objective:** Runtime management commands for operators  
**Estimated Effort:** 6 hours  
**Status:** Planned  

---

## Objective

Create an `AdminPlugin` that provides runtime management commands accessible via CyTube chat. Enable operators to reload plugins, check status, and access metrics without SSH access or bot restarts.

**Target State**:
- Commands: `!admin reload`, `!admin status`, `!admin restart`, `!admin list`, `!admin metrics`
- Permission system (only authorized users)
- Confirmation prompts for destructive operations
- Audit logging of all admin actions

---

## Context

### Current State (Post-Sortie 3)

**What Works** ✅:
- Hot-reload implemented (`PluginManager.reload_plugin()`)
- Metrics dashboard available (`http://localhost:8080`)
- Metrics collector tracking all plugins
- JSON API endpoints available

**What's Missing** ❌:
- No way to trigger reload from CyTube chat
- Must SSH in to reload plugins
- No runtime status checks
- No access control (anyone could reload if commands existed)

### Why Admin Commands Matter

**Before Admin Commands**:
```
Ops: "I need to reload dice-roller"
Ops: *SSHs into server*
Ops: *Opens Python REPL*
Ops: >>> from rosey import bot
Ops: >>> await bot.plugin_manager.reload_plugin('dice-roller')
Ops: *Waits*
Ops: *Checks if it worked*
Time: 5 minutes, requires SSH access
```

**With Admin Commands**:
```
Ops: "I need to reload dice-roller"
Ops: !admin reload dice-roller
Bot: "Reload dice-roller v1.0 → v1.1? Type 'yes' to confirm"
Ops: yes
Bot: "✅ Reloaded dice-roller v1.0 → v1.1 (3.2s)"
Time: 10 seconds, no SSH required
```

---

## Technical Design

### AdminPlugin Class

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
import time
from typing import Dict, Optional

@dataclass
class PendingConfirmation:
    """Pending admin action awaiting confirmation"""
    user: str
    command: str
    args: dict
    expires_at: float
    
class AdminPlugin:
    """
    Admin commands for bot management
    
    Commands:
    - !admin reload <plugin>    → Hot-reload plugin
    - !admin restart <plugin>   → Cold restart plugin
    - !admin status [plugin]    → Show plugin status
    - !admin list               → List all plugins
    - !admin metrics            → Link to dashboard
    - !admin help               → Show help
    """
    
    def __init__(self, event_bus: EventBus, config: dict, rosey: 'Rosey'):
        self.event_bus = event_bus
        self.config = config
        self.rosey = rosey
        
        # Admin users (from config)
        self.admins = set(config.get('admins', []))
        if config.get('owner'):
            self.admins.add(config['owner'])
            
        # Pending confirmations (user -> confirmation)
        self.pending_confirmations: Dict[str, PendingConfirmation] = {}
        
        # Audit log (last 100 actions)
        self.audit_log: deque = deque(maxlen=100)
        
        # Rate limiting (prevent spam)
        self.last_command_time: Dict[str, float] = {}
        self.rate_limit_seconds = 5
        
    async def start(self):
        """Subscribe to admin commands"""
        await self.event_bus.subscribe(
            'rosey.command.admin.*',
            self.handle_command
        )
        logger.info("✅ Admin plugin started")
        
    async def handle_command(self, event: dict):
        """Route admin commands"""
        user = event['user']
        message = event['message']
        channel = event['channel']
        
        # Permission check
        if not self._is_admin(user):
            await self._send_error(
                channel,
                "❌ Admin permission required"
            )
            self._audit_log(user, "DENIED", message)
            return
            
        # Rate limit check
        if self._is_rate_limited(user):
            await self._send_error(
                channel,
                "⏱️ Please wait before running another admin command"
            )
            return
            
        # Update rate limit
        self.last_command_time[user] = time.time()
        
        # Parse command
        parts = message.split()
        if len(parts) < 2:
            await self.cmd_help(user, channel)
            return
            
        subcommand = parts[1].lower()
        args = parts[2:] if len(parts) > 2 else []
        
        # Check for confirmation response
        if subcommand == 'yes' or message.lower() == 'yes':
            await self.handle_confirmation(user, channel)
            return
            
        # Route to subcommand handler
        handlers = {
            'reload': self.cmd_reload,
            'restart': self.cmd_restart,
            'status': self.cmd_status,
            'list': self.cmd_list,
            'metrics': self.cmd_metrics,
            'help': self.cmd_help,
        }
        
        handler = handlers.get(subcommand)
        if handler:
            try:
                await handler(user, channel, args)
            except Exception as e:
                logger.error(f"Admin command error: {e}", exc_info=True)
                await self._send_error(
                    channel,
                    f"❌ Error: {str(e)}"
                )
        else:
            await self._send_error(
                channel,
                f"❌ Unknown command: {subcommand}. Try !admin help"
            )
            
    # ========== Command Handlers ==========
    
    async def cmd_reload(self, user: str, channel: str, args: list):
        """!admin reload <plugin>"""
        if not args:
            await self._send_error(
                channel,
                "❌ Usage: !admin reload <plugin>"
            )
            return
            
        plugin_name = args[0]
        
        # Validate plugin exists
        if plugin_name not in self.rosey.plugin_manager.plugins:
            await self._send_error(
                channel,
                f"❌ Plugin '{plugin_name}' not found. "
                f"Use !admin list to see available plugins."
            )
            return
            
        # Get current version
        plugin = self.rosey.plugin_manager.plugins[plugin_name]
        old_version = plugin.version
        
        # Request confirmation
        confirmation = PendingConfirmation(
            user=user,
            command='reload',
            args={'plugin_name': plugin_name, 'old_version': old_version},
            expires_at=time.time() + 30,  # 30s timeout
        )
        self.pending_confirmations[user] = confirmation
        
        await self._send_message(
            channel,
            f"🔄 Reload {plugin_name} (v{old_version})? "
            f"Type **yes** to confirm (30s timeout)"
        )
        
    async def cmd_restart(self, user: str, channel: str, args: list):
        """!admin restart <plugin>"""
        if not args:
            await self._send_error(
                channel,
                "❌ Usage: !admin restart <plugin>"
            )
            return
            
        plugin_name = args[0]
        
        # Validate plugin exists
        if plugin_name not in self.rosey.plugin_manager.plugins:
            await self._send_error(
                channel,
                f"❌ Plugin '{plugin_name}' not found"
            )
            return
            
        # Request confirmation (restart has downtime)
        confirmation = PendingConfirmation(
            user=user,
            command='restart',
            args={'plugin_name': plugin_name},
            expires_at=time.time() + 30,
        )
        self.pending_confirmations[user] = confirmation
        
        await self._send_message(
            channel,
            f"♻️ Restart {plugin_name}? "
            f"**This will cause brief downtime.** "
            f"Type **yes** to confirm (30s timeout)"
        )
        
    async def cmd_status(self, user: str, channel: str, args: list):
        """!admin status [plugin]"""
        if args:
            # Single plugin status
            plugin_name = args[0]
            await self._show_plugin_status(channel, plugin_name)
        else:
            # All plugins status
            await self._show_all_status(channel)
            
    async def cmd_list(self, user: str, channel: str, args: list):
        """!admin list"""
        plugins = self.rosey.plugin_manager.plugins
        
        if not plugins:
            await self._send_message(channel, "No plugins loaded")
            return
            
        lines = ["**Loaded Plugins:**"]
        for name, plugin in sorted(plugins.items()):
            state_emoji = "✅" if plugin.state.name == "RUNNING" else "❌"
            lines.append(
                f"• {state_emoji} **{name}** v{plugin.version} "
                f"({plugin.state.name})"
            )
            
        await self._send_message(channel, '\n'.join(lines))
        
    async def cmd_metrics(self, user: str, channel: str, args: list):
        """!admin metrics"""
        dashboard_url = (
            f"http://{self.rosey.config.dashboard.host}:"
            f"{self.rosey.config.dashboard.port}"
        )
        await self._send_message(
            channel,
            f"📊 **Metrics Dashboard:** {dashboard_url}"
        )
        
    async def cmd_help(self, user: str, channel: str, args: list = None):
        """!admin help"""
        help_text = """**Admin Commands:**
• `!admin reload <plugin>` - Hot-reload plugin (zero downtime)
• `!admin restart <plugin>` - Cold restart plugin (brief downtime)
• `!admin status [plugin]` - Show plugin status
• `!admin list` - List all loaded plugins
• `!admin metrics` - Link to metrics dashboard
• `!admin help` - Show this help"""
        
        await self._send_message(channel, help_text)
        
    # ========== Confirmation Handler ==========
    
    async def handle_confirmation(self, user: str, channel: str):
        """Handle 'yes' confirmation response"""
        if user not in self.pending_confirmations:
            # No pending confirmation
            return
            
        confirmation = self.pending_confirmations[user]
        
        # Check expiration
        if time.time() > confirmation.expires_at:
            del self.pending_confirmations[user]
            await self._send_error(
                channel,
                "❌ Confirmation expired. Please try again."
            )
            return
            
        # Execute confirmed action
        del self.pending_confirmations[user]
        
        if confirmation.command == 'reload':
            await self._do_reload(user, channel, confirmation.args)
        elif confirmation.command == 'restart':
            await self._do_restart(user, channel, confirmation.args)
            
    async def _do_reload(self, user: str, channel: str, args: dict):
        """Execute hot-reload"""
        plugin_name = args['plugin_name']
        old_version = args['old_version']
        
        await self._send_message(
            channel,
            f"🔄 Reloading {plugin_name}..."
        )
        
        start_time = time.time()
        
        try:
            # Perform reload
            result = await self.rosey.plugin_manager.reload_plugin(plugin_name)
            
            duration = time.time() - start_time
            
            if result.success:
                await self._send_message(
                    channel,
                    f"✅ Reloaded {plugin_name} "
                    f"v{result.old_version} → v{result.new_version} "
                    f"({duration:.1f}s)"
                )
                self._audit_log(user, "RELOAD_SUCCESS", plugin_name)
            else:
                await self._send_error(
                    channel,
                    f"❌ Reload failed: {result.error}"
                )
                self._audit_log(user, "RELOAD_FAILED", f"{plugin_name}: {result.error}")
                
        except Exception as e:
            logger.error(f"Reload error: {e}", exc_info=True)
            await self._send_error(
                channel,
                f"❌ Reload error: {str(e)}"
            )
            self._audit_log(user, "RELOAD_ERROR", f"{plugin_name}: {e}")
            
    async def _do_restart(self, user: str, channel: str, args: dict):
        """Execute cold restart"""
        plugin_name = args['plugin_name']
        
        await self._send_message(
            channel,
            f"♻️ Restarting {plugin_name}..."
        )
        
        start_time = time.time()
        
        try:
            # Stop then start (cold restart)
            await self.rosey.plugin_manager.stop_plugin(plugin_name)
            await asyncio.sleep(0.5)  # Brief pause
            await self.rosey.plugin_manager.start_plugin(plugin_name)
            
            duration = time.time() - start_time
            
            await self._send_message(
                channel,
                f"✅ Restarted {plugin_name} ({duration:.1f}s)"
            )
            self._audit_log(user, "RESTART", plugin_name)
            
        except Exception as e:
            logger.error(f"Restart error: {e}", exc_info=True)
            await self._send_error(
                channel,
                f"❌ Restart error: {str(e)}"
            )
            self._audit_log(user, "RESTART_ERROR", f"{plugin_name}: {e}")
            
    # ========== Status Display ==========
    
    async def _show_plugin_status(self, channel: str, plugin_name: str):
        """Show detailed status for single plugin"""
        if plugin_name not in self.rosey.plugin_manager.plugins:
            await self._send_error(
                channel,
                f"❌ Plugin '{plugin_name}' not found"
            )
            return
            
        plugin = self.rosey.plugin_manager.plugins[plugin_name]
        metrics = await plugin.get_metrics()
        
        # Get aggregates (last 5 minutes)
        aggregates = self.rosey.metrics_collector.get_aggregates(
            plugin_name,
            duration=timedelta(minutes=5)
        )
        
        # Format status
        state_emoji = "✅" if metrics.state == "RUNNING" else "❌"
        uptime = self._format_duration(metrics.uptime)
        
        lines = [
            f"**{plugin_name}** {state_emoji}",
            f"• Version: {metrics.version}",
            f"• PID: {metrics.pid or 'N/A'}",
            f"• State: {metrics.state}",
            f"• Uptime: {uptime}",
            f"• CPU: {metrics.cpu_percent:.1f}%",
            f"• Memory: {metrics.memory_mb:.1f} MB",
            f"• Events: {metrics.event_count:,}",
            f"• Crashes: {metrics.crash_count}",
        ]
        
        if aggregates:
            lines.append(
                f"• Avg CPU (5m): {aggregates.cpu_avg:.1f}%"
            )
            
        await self._send_message(channel, '\n'.join(lines))
        
    async def _show_all_status(self, channel: str):
        """Show brief status for all plugins"""
        plugins = self.rosey.plugin_manager.plugins
        system = self.rosey.metrics_collector.get_system_metrics()
        
        lines = [
            f"**Bot Status**",
            f"• Uptime: {system.to_dict()['bot_uptime_human']}",
            f"• Plugins: {system.plugins_running}/{system.total_plugins} running",
            f"• Total Events: {system.total_events:,}",
            "",
            "**Plugins:**"
        ]
        
        for name, plugin in sorted(plugins.items()):
            state_emoji = "✅" if plugin.state.name == "RUNNING" else "❌"
            metrics = await plugin.get_metrics()
            lines.append(
                f"• {state_emoji} **{name}** "
                f"v{metrics.version} - "
                f"{metrics.cpu_percent:.1f}% CPU, "
                f"{metrics.memory_mb:.0f} MB"
            )
            
        await self._send_message(channel, '\n'.join(lines))
        
    # ========== Helpers ==========
    
    def _is_admin(self, user: str) -> bool:
        """Check if user has admin permissions"""
        return user in self.admins
        
    def _is_rate_limited(self, user: str) -> bool:
        """Check if user is rate limited"""
        if user not in self.last_command_time:
            return False
            
        elapsed = time.time() - self.last_command_time[user]
        return elapsed < self.rate_limit_seconds
        
    def _audit_log(self, user: str, action: str, details: str):
        """Log admin action for audit trail"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'user': user,
            'action': action,
            'details': details,
        }
        self.audit_log.append(entry)
        logger.info(f"AUDIT: {user} {action} {details}")
        
    async def _send_message(self, channel: str, message: str):
        """Send message to CyTube channel"""
        await self.event_bus.publish('cytube.send.message', {
            'channel': channel,
            'message': message,
        })
        
    async def _send_error(self, channel: str, message: str):
        """Send error message to CyTube channel"""
        await self._send_message(channel, message)
        
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration as human-readable string"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m"
        elif seconds < 86400:
            h = int(seconds / 3600)
            m = int((seconds % 3600) / 60)
            return f"{h}h {m}m"
        else:
            d = int(seconds / 86400)
            h = int((seconds % 86400) / 3600)
            return f"{d}d {h}h"
```

---

## Implementation Plan

### Phase 1: Core Plugin Structure (2h)

1. Create `AdminPlugin` class
2. Implement `start()` lifecycle
3. Implement `handle_command()` router
4. Add permission checking
5. Add rate limiting

### Phase 2: Command Handlers (2h)

1. Implement `cmd_reload()` with confirmation
2. Implement `cmd_restart()` with confirmation
3. Implement `cmd_status()` (single and all)
4. Implement `cmd_list()`
5. Implement `cmd_metrics()` and `cmd_help()`

### Phase 3: Confirmation System (1h)

1. Implement `handle_confirmation()`
2. Implement `_do_reload()` executor
3. Implement `_do_restart()` executor
4. Add timeout handling
5. Test confirmation flow

### Phase 4: Audit & Polish (1h)

1. Implement audit logging
2. Add error handling
3. Format output messages
4. Test all commands end-to-end

---

## Testing Strategy

### Unit Tests (2 new tests)

**Test 1: Permission Checks**
```python
async def test_admin_permission_denied():
    """Non-admin can't run admin commands"""
    # Arrange: Admin plugin with config (only 'admin_user' is admin)
    config = {'admins': ['admin_user']}
    plugin = AdminPlugin(event_bus, config, rosey)
    await plugin.start()
    
    # Act: Non-admin tries reload
    await event_bus.publish('rosey.command.admin.reload', {
        'user': 'normal_user',
        'message': '!admin reload dice-roller',
        'channel': 'test',
    })
    
    await asyncio.sleep(0.1)
    
    # Assert: Permission denied message sent
    # (Check via event_bus mock)
    assert "Admin permission required" in sent_messages
```

**Test 2: Reload Command**
```python
async def test_admin_reload_command():
    """Admin can reload plugin via command"""
    # Arrange: Start bot with dice-roller v1.0
    bot = Rosey(config)
    await bot.start()
    
    # Deploy dice-roller v1.1
    _update_plugin_version('dice-roller', '1.1')
    
    # Act: Admin reloads
    await bot.event_bus.publish('rosey.command.admin.reload', {
        'user': 'admin_user',
        'message': '!admin reload dice-roller',
        'channel': 'test',
    })
    
    await asyncio.sleep(0.1)
    
    # Confirm
    await bot.event_bus.publish('rosey.command.admin.reload', {
        'user': 'admin_user',
        'message': 'yes',
        'channel': 'test',
    })
    
    await asyncio.sleep(5)  # Wait for reload
    
    # Assert: Plugin reloaded
    assert bot.plugin_manager.plugins['dice-roller'].version == '1.1'
    
    await bot.stop()
```

### Manual Testing

**Test All Commands**:
```
# In CyTube chat (as admin user):

!admin help
→ Shows help text

!admin list
→ Shows all plugins with versions

!admin status
→ Shows all plugins brief status

!admin status dice-roller
→ Shows dice-roller detailed status

!admin metrics
→ Shows dashboard link

!admin reload dice-roller
→ Asks for confirmation
yes
→ Reloads plugin, shows success message

!admin restart dice-roller
→ Asks for confirmation (warns about downtime)
yes
→ Restarts plugin, shows success message
```

---

## Quality Gates

**Must Pass Before Merge**:
- [ ] All 2 new tests passing
- [ ] All commands work (verified manually)
- [ ] Permission checks work (non-admin denied)
- [ ] Confirmation prompts work
- [ ] Rate limiting works (try spam commands)
- [ ] Audit log populated (check logs)
- [ ] Code coverage >80% for new code

**Security Validation**:
- [ ] Non-admin users denied
- [ ] Confirmation required for destructive operations
- [ ] Rate limiting prevents spam
- [ ] Audit log records all actions

---

## Integration

### Wire into rosey.py

```python
class Rosey:
    async def start(self):
        # ... existing startup ...
        
        # Start admin plugin (NEW)
        if self.config.admins:
            self.admin_plugin = AdminPlugin(
                self.event_bus,
                self.config,
                self  # Pass self for access to manager/collector
            )
            await self.admin_plugin.start()
            logger.info("✅ Admin plugin started")
```

### Config Schema

```json
{
  "owner": "bot_owner_username",
  "admins": [
    "operator1",
    "operator2"
  ]
}
```

---

## Security Considerations

**Permission System**:
- Only users in `config.admins` or `config.owner` can run commands
- Permission check happens before any action
- Denied attempts logged for audit

**Rate Limiting**:
- 5-second cooldown between commands per user
- Prevents accidental spam
- Prevents malicious reload spam

**Confirmation Prompts**:
- Destructive operations (`reload`, `restart`) require confirmation
- 30-second timeout (prevents stale confirmations)
- Clear warning for operations with downtime

**Audit Logging**:
- All admin actions logged with timestamp, user, action
- Last 100 actions kept in memory
- Written to bot logs (persistent)
- Enables accountability and debugging

---

## Follow-Up Work

**Sprint 24 Enhancements**:
- `!admin config <plugin> <key> <value>` - Runtime config changes
- `!admin logs <plugin>` - Show recent plugin logs
- `!admin ban <user>` - Ban user from bot commands
- Webhook notifications (Slack/Discord) for admin actions

---

**End of Sortie 4 Spec**
