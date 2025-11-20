# Sortie 6b: Plugin Sandbox - Permission System

**Sprint:** 6a-quicksilver  
**Complexity:** ⭐⭐⭐⭐☆ (Security Architecture)  
**Estimated Time:** 3-4 hours  
**Priority:** CRITICAL  
**Dependencies:** Sortie 6a (Process Isolation)

---

## Objective

Implement comprehensive permission system for plugins including NATS subject allowlists, resource limits enforcement, capability-based security for filesystem/network access, and runtime permission validation.

---

## Security Model Overview

### Defense in Depth

```
Layer 1: Process Isolation (6a) ✅
  └─ Separate process per plugin
  └─ Crash isolation
  └─ Memory isolation

Layer 2: Permission System (6b) ← THIS SORTIE
  └─ NATS subject allowlists (what can subscribe/publish)
  └─ Resource limits (CPU, memory, disk)
  └─ Capability grants (filesystem, network, external APIs)
  └─ Runtime validation

Layer 3: State Isolation (6c - future)
  └─ Per-plugin storage
  └─ No cross-plugin data access

Layer 4: API Gateway (6e - future)
  └─ Rate limiting
  └─ OAuth token management
  └─ Audit logging
```

### Threat Model

**What we're protecting against:**

1. **Malicious plugins** - Untrusted code trying to access sensitive data
2. **Buggy plugins** - Well-intentioned but poorly written code causing harm
3. **Resource exhaustion** - Plugin consuming excessive CPU/memory
4. **Privilege escalation** - Plugin trying to gain unauthorized access
5. **Data exfiltration** - Plugin attempting to leak sensitive information

**What we're NOT protecting against (yet):**

- Network-level attacks (no network isolation yet)
- Sophisticated timing attacks
- Hardware-level exploits
- Social engineering

---

## Permission Types

### 1. NATS Subject Permissions (Mandatory)

**Every plugin gets:**
- ✅ Subscribe: `rosey.commands.{plugin_name}.execute` (own commands)
- ✅ Publish: `rosey.commands.{plugin_name}.result` (command results)
- ✅ Publish: `rosey.commands.{plugin_name}.error` (errors)
- ✅ Publish: `rosey.plugins.{plugin_name}.*` (plugin events)

**Optional grants:**
- 🔒 Subscribe: `rosey.events.*` (normalized events - user join, messages, etc.)
- 🔒 Subscribe: `rosey.platform.{platform}.*` (platform-specific events)
- 🔒 Publish: `rosey.platform.{platform}.send.*` (send to platforms directly)
- 🔒 Subscribe: `rosey.plugins.{other_plugin}.*` (inter-plugin communication)

### 2. Resource Limits (Mandatory)

- **CPU**: Max percentage (default: 50% of one core)
- **Memory**: Max RAM (default: 256MB)
- **Process lifetime**: Max uptime before forced restart (default: 24 hours)
- **Message rate**: Max messages/second (default: 100/sec)

### 3. Capabilities (Opt-in)

- 🔒 **Filesystem Read**: Access to specific directories
- 🔒 **Filesystem Write**: Write to specific directories (temp, plugin data)
- 🔒 **Network Access**: Make external HTTP requests
- 🔒 **External API**: Access to specific external APIs (MyTurn, calendar, etc.)
- 🔒 **Database Access**: Read/write to plugin storage

---

## Technical Implementation

### Task 6b.1: Plugin Manifest

**File:** `bot/rosey/plugins/plugin_manifest.py`

```python
"""
Plugin manifest - Declares plugin permissions and requirements
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class Capability(Enum):
    """Plugin capabilities (opt-in permissions)"""
    
    # Filesystem
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    FILESYSTEM_TEMP = "filesystem.temp"  # Write to temp directory only
    
    # Network
    NETWORK_HTTP = "network.http"        # Make HTTP requests
    NETWORK_WEBSOCKET = "network.websocket"
    
    # External APIs
    API_CALENDAR = "api.calendar"        # Calendar API access
    API_EXTERNAL = "api.external"        # Generic external API
    
    # Database
    DATABASE_READ = "database.read"      # Read from plugin DB
    DATABASE_WRITE = "database.write"    # Write to plugin DB
    
    # Inter-plugin
    PLUGIN_BROADCAST = "plugin.broadcast"  # Publish to other plugins
    PLUGIN_LISTEN = "plugin.listen"        # Subscribe to other plugins


@dataclass
class ResourceLimits:
    """Resource limit configuration"""
    
    max_cpu_percent: float = 50.0      # Max CPU % (50 = half a core)
    max_memory_mb: int = 256            # Max memory in MB
    max_uptime_hours: int = 24          # Max uptime before restart
    max_message_rate: int = 100         # Max messages per second


@dataclass
class SubjectPermission:
    """NATS subject permission"""
    
    pattern: str                        # Subject pattern (e.g., "rosey.events.*")
    allow_subscribe: bool = False       # Can subscribe to this pattern
    allow_publish: bool = False         # Can publish to this pattern


@dataclass
class PluginManifest:
    """
    Plugin manifest - Declares what plugin needs
    
    Example manifest:
    
        manifest = PluginManifest(
            name="calendar",
            version="1.0.0",
            description="Calendar event manager",
            author="YourName",
            
            # Request specific event subscriptions
            subject_permissions=[
                SubjectPermission("rosey.events.message", allow_subscribe=True),
                SubjectPermission("rosey.events.user.join", allow_subscribe=True),
            ],
            
            # Request capabilities
            capabilities=[
                Capability.FILESYSTEM_WRITE,  # Need to write ICS files
                Capability.API_CALENDAR,       # Need calendar API access
            ],
            
            # Custom resource limits
            resource_limits=ResourceLimits(
                max_cpu_percent=25.0,    # Only need 25% CPU
                max_memory_mb=128,       # Only need 128MB RAM
            )
        )
    """
    
    # Basic info
    name: str
    version: str
    description: str
    author: str = "Unknown"
    
    # Permissions
    subject_permissions: List[SubjectPermission] = field(default_factory=list)
    capabilities: List[Capability] = field(default_factory=list)
    
    # Resource limits
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    
    # Metadata
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: str = "Unknown"
    
    def __post_init__(self):
        """Validate manifest"""
        if not self.name:
            raise ValueError("Plugin name required")
        
        if not self.name.isidentifier():
            raise ValueError(f"Invalid plugin name: {self.name} (must be valid Python identifier)")
        
        if not self.version:
            raise ValueError("Plugin version required")
    
    def get_allowed_subscribe_patterns(self) -> List[str]:
        """Get all patterns plugin can subscribe to"""
        patterns = [
            # Always allowed: own commands
            f"rosey.commands.{self.name}.execute",
        ]
        
        # Add requested permissions
        for perm in self.subject_permissions:
            if perm.allow_subscribe:
                patterns.append(perm.pattern)
        
        return patterns
    
    def get_allowed_publish_patterns(self) -> List[str]:
        """Get all patterns plugin can publish to"""
        patterns = [
            # Always allowed: own results/errors/events
            f"rosey.commands.{self.name}.result",
            f"rosey.commands.{self.name}.error",
            f"rosey.plugins.{self.name}.*",
        ]
        
        # Add requested permissions
        for perm in self.subject_permissions:
            if perm.allow_publish:
                patterns.append(perm.pattern)
        
        return patterns
    
    def has_capability(self, capability: Capability) -> bool:
        """Check if plugin has specific capability"""
        return capability in self.capabilities
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "subject_permissions": [
                {
                    "pattern": p.pattern,
                    "allow_subscribe": p.allow_subscribe,
                    "allow_publish": p.allow_publish
                }
                for p in self.subject_permissions
            ],
            "capabilities": [c.value for c in self.capabilities],
            "resource_limits": {
                "max_cpu_percent": self.resource_limits.max_cpu_percent,
                "max_memory_mb": self.resource_limits.max_memory_mb,
                "max_uptime_hours": self.resource_limits.max_uptime_hours,
                "max_message_rate": self.resource_limits.max_message_rate,
            },
            "homepage": self.homepage,
            "repository": self.repository,
            "license": self.license,
        }
```

---

### Task 6b.2: Permission Validator

**File:** `bot/rosey/plugins/permission_validator.py`

```python
"""
Permission validator - Runtime permission enforcement
"""
import logging
import fnmatch
from typing import List, Optional

from bot.rosey.plugins.plugin_manifest import PluginManifest, Capability

logger = logging.getLogger(__name__)


class PermissionDeniedError(Exception):
    """Raised when plugin attempts unauthorized action"""
    pass


class PermissionValidator:
    """
    Validates plugin permissions at runtime
    
    Enforces:
    - NATS subject allowlists
    - Capability requirements
    - Resource limits (checked by PluginProcess)
    
    Example:
        validator = PermissionValidator(manifest)
        
        # Check subscription
        validator.validate_subscribe("rosey.events.message")
        
        # Check publish
        validator.validate_publish("rosey.plugins.myplugin.event")
        
        # Check capability
        validator.validate_capability(Capability.FILESYSTEM_WRITE)
    """
    
    def __init__(self, manifest: PluginManifest):
        """
        Initialize validator
        
        Args:
            manifest: Plugin manifest with declared permissions
        """
        self.manifest = manifest
        self.plugin_name = manifest.name
        
        # Compile patterns for fast matching
        self._subscribe_patterns = manifest.get_allowed_subscribe_patterns()
        self._publish_patterns = manifest.get_allowed_publish_patterns()
        
        logger.info(f"Permission validator for '{self.plugin_name}' initialized")
        logger.debug(f"  Subscribe patterns: {self._subscribe_patterns}")
        logger.debug(f"  Publish patterns: {self._publish_patterns}")
    
    def validate_subscribe(self, subject: str):
        """
        Validate plugin can subscribe to subject
        
        Args:
            subject: NATS subject to subscribe to
        
        Raises:
            PermissionDeniedError: If not allowed
        """
        if not self._matches_any_pattern(subject, self._subscribe_patterns):
            logger.warning(
                f"Plugin '{self.plugin_name}' denied subscription to: {subject}"
            )
            raise PermissionDeniedError(
                f"Plugin '{self.plugin_name}' not allowed to subscribe to '{subject}'. "
                f"Declare permission in manifest: "
                f"SubjectPermission('{subject}', allow_subscribe=True)"
            )
        
        logger.debug(f"Plugin '{self.plugin_name}' allowed to subscribe: {subject}")
    
    def validate_publish(self, subject: str):
        """
        Validate plugin can publish to subject
        
        Args:
            subject: NATS subject to publish to
        
        Raises:
            PermissionDeniedError: If not allowed
        """
        if not self._matches_any_pattern(subject, self._publish_patterns):
            logger.warning(
                f"Plugin '{self.plugin_name}' denied publish to: {subject}"
            )
            raise PermissionDeniedError(
                f"Plugin '{self.plugin_name}' not allowed to publish to '{subject}'. "
                f"Declare permission in manifest: "
                f"SubjectPermission('{subject}', allow_publish=True)"
            )
        
        logger.debug(f"Plugin '{self.plugin_name}' allowed to publish: {subject}")
    
    def validate_capability(self, capability: Capability):
        """
        Validate plugin has capability
        
        Args:
            capability: Required capability
        
        Raises:
            PermissionDeniedError: If capability not granted
        """
        if not self.manifest.has_capability(capability):
            logger.warning(
                f"Plugin '{self.plugin_name}' denied capability: {capability.value}"
            )
            raise PermissionDeniedError(
                f"Plugin '{self.plugin_name}' does not have capability '{capability.value}'. "
                f"Add to manifest: capabilities=[Capability.{capability.name}]"
            )
        
        logger.debug(f"Plugin '{self.plugin_name}' has capability: {capability.value}")
    
    def _matches_any_pattern(self, subject: str, patterns: List[str]) -> bool:
        """
        Check if subject matches any pattern
        
        Supports wildcards:
        - * matches single token (e.g., "rosey.events.*" matches "rosey.events.message")
        - > matches multiple tokens (not used in patterns, but NATS supports it)
        
        Args:
            subject: Subject to check
            patterns: List of allowed patterns
        
        Returns:
            True if matches any pattern
        """
        for pattern in patterns:
            # Convert NATS wildcards to fnmatch wildcards
            # NATS: rosey.events.* -> fnmatch: rosey.events.*
            # NATS: rosey.events.> -> fnmatch: rosey.events.*
            fnmatch_pattern = pattern.replace('.>', '.*').replace('.*', '.*')
            
            if fnmatch.fnmatch(subject, fnmatch_pattern):
                return True
        
        return False
    
    def check_resource_limits(self, stats: dict) -> List[str]:
        """
        Check if plugin is within resource limits
        
        Args:
            stats: Resource usage stats from PluginProcess.get_stats()
        
        Returns:
            List of violations (empty if within limits)
        """
        violations = []
        limits = self.manifest.resource_limits
        
        # Check CPU
        cpu_percent = stats.get("cpu_percent", 0)
        if cpu_percent > limits.max_cpu_percent:
            violations.append(
                f"CPU usage {cpu_percent:.1f}% exceeds limit {limits.max_cpu_percent}%"
            )
        
        # Check memory
        memory_mb = stats.get("memory_mb", 0)
        if memory_mb > limits.max_memory_mb:
            violations.append(
                f"Memory usage {memory_mb:.1f}MB exceeds limit {limits.max_memory_mb}MB"
            )
        
        # Check uptime
        uptime_hours = stats.get("uptime_seconds", 0) / 3600
        if uptime_hours > limits.max_uptime_hours:
            violations.append(
                f"Uptime {uptime_hours:.1f}h exceeds limit {limits.max_uptime_hours}h"
            )
        
        return violations
```

---

### Task 6b.3: Secure PluginInterface

**Update:** `bot/rosey/plugins/plugin_interface.py`

```python
"""
Update PluginInterface to use PermissionValidator
"""

# Add to imports:
from bot.rosey.plugins.plugin_manifest import PluginManifest, Capability
from bot.rosey.plugins.permission_validator import PermissionValidator, PermissionDeniedError

# Add to PluginInterface class:

class PluginInterface(ABC):
    """
    Base class for all Rosey plugins (UPDATED with permissions)
    """
    
    def __init__(self, nats_url: str = None, nats_token: str = None):
        # ... existing init code ...
        
        # Permission system
        self._manifest: Optional[PluginManifest] = None
        self._validator: Optional[PermissionValidator] = None
    
    # New abstract method
    @abstractmethod
    def get_manifest(self) -> PluginManifest:
        """
        Return plugin manifest with permission declarations
        
        Example:
            def get_manifest(self) -> PluginManifest:
                return PluginManifest(
                    name=self.plugin_name,
                    version="1.0.0",
                    description="My plugin",
                    author="Me",
                    subject_permissions=[
                        SubjectPermission(
                            "rosey.events.message",
                            allow_subscribe=True
                        ),
                    ],
                    capabilities=[
                        Capability.FILESYSTEM_WRITE,
                    ]
                )
        """
        pass
    
    async def connect(self):
        """Connect to NATS (UPDATED with permission validation)"""
        # Get manifest
        self._manifest = self.get_manifest()
        self._validator = PermissionValidator(self._manifest)
        
        logger.info(f"Plugin '{self.plugin_name}' manifest loaded")
        logger.info(f"  Version: {self._manifest.version}")
        logger.info(f"  Capabilities: {[c.value for c in self._manifest.capabilities]}")
        
        # ... existing connection code ...
        
        # Subscribe to commands (with validation)
        command_subject = Subjects.plugin_command(self.plugin_name, "execute")
        
        try:
            self._validator.validate_subscribe(command_subject)
            await self.event_bus.subscribe(command_subject, self._handle_command_wrapper)
        except PermissionDeniedError as e:
            logger.error(f"Permission denied during connect: {e}")
            raise
    
    # UPDATED publish methods with validation
    
    async def publish_result(
        self, 
        data: Dict[str, Any], 
        correlation_id: str = None,
        response_channel: Dict[str, Any] = None
    ):
        """Publish command result (UPDATED with validation)"""
        subject = Subjects.plugin_command(self.plugin_name, "result")
        
        # Validate permission
        try:
            self._validator.validate_publish(subject)
        except PermissionDeniedError as e:
            logger.error(f"Cannot publish result: {e}")
            raise
        
        # ... rest of existing code ...
    
    async def subscribe_to_events(self, event_types: List[str] = None):
        """Subscribe to normalized events (UPDATED with validation)"""
        if event_types:
            for event_type in event_types:
                subject = f"{Subjects.EVENTS}.{event_type}"
                
                # Validate permission
                try:
                    self._validator.validate_subscribe(subject)
                    await self.event_bus.subscribe(subject, self.on_event)
                    logger.info(f"Plugin '{self.plugin_name}' subscribed to {subject}")
                except PermissionDeniedError as e:
                    logger.error(f"Cannot subscribe to {subject}: {e}")
                    # Don't raise - allow plugin to continue with other subscriptions
        else:
            # Subscribe to all events
            subject = Subjects.EVENTS_ALL
            
            try:
                self._validator.validate_subscribe(subject)
                await self.event_bus.subscribe(subject, self.on_event)
                logger.info(f"Plugin '{self.plugin_name}' subscribed to all events")
            except PermissionDeniedError as e:
                logger.error(f"Cannot subscribe to all events: {e}")
                raise
    
    # NEW: Capability checking methods for plugin authors
    
    def require_capability(self, capability: Capability):
        """
        Assert plugin has capability (raises if not)
        
        Use at start of methods that need specific capabilities:
        
        Example:
            async def write_file(self, path: str, data: str):
                self.require_capability(Capability.FILESYSTEM_WRITE)
                # ... write file ...
        """
        if self._validator:
            self._validator.validate_capability(capability)
    
    def has_capability(self, capability: Capability) -> bool:
        """
        Check if plugin has capability (returns bool, doesn't raise)
        
        Example:
            if self.has_capability(Capability.NETWORK_HTTP):
                await self.fetch_from_api()
            else:
                logger.warning("Network access not available")
        """
        if self._validator:
            try:
                self._validator.validate_capability(capability)
                return True
            except PermissionDeniedError:
                return False
        return False
```

---

### Task 6b.4: Updated Example Plugin with Manifest

**File:** `bot/rosey/plugins/examples/calendar_plugin.py`

```python
"""
Calendar plugin - Demonstrates permission system

This plugin:
- Listens for messages about meetings
- Generates ICS files
- Sends files to users

Requires:
- Subscribe to messages
- Filesystem write (for ICS generation)
- External API (for calendar service)
"""
from bot.rosey.plugins.plugin_interface import PluginInterface, run_plugin
from bot.rosey.plugins.plugin_manifest import (
    PluginManifest, 
    SubjectPermission, 
    Capability,
    ResourceLimits
)
from bot.rosey.core.events import Event
import re
from datetime import datetime


class CalendarPlugin(PluginInterface):
    """
    Calendar event manager
    
    Usage:
        User in Slack thread: "Let's meet Thursday at 2pm at Building A"
        Bot: !calendar create
        -> Generates ICS file and sends to thread participants
    """
    
    @property
    def plugin_name(self) -> str:
        return "calendar"
    
    def get_manifest(self) -> PluginManifest:
        """Declare what this plugin needs"""
        return PluginManifest(
            name="calendar",
            version="1.0.0",
            description="Calendar event manager - creates ICS files from meeting decisions",
            author="Rosey Team",
            
            # Permission requests
            subject_permissions=[
                # Need to listen to all messages to detect meeting discussions
                SubjectPermission(
                    pattern="rosey.events.message",
                    allow_subscribe=True
                ),
                # Need to listen to user joins (to know thread participants)
                SubjectPermission(
                    pattern="rosey.events.user.join",
                    allow_subscribe=True
                ),
                # Need to send messages back to platform (Slack, etc.)
                SubjectPermission(
                    pattern="rosey.platform.*.send.chat",
                    allow_publish=True
                ),
            ],
            
            # Capability requests
            capabilities=[
                Capability.FILESYSTEM_WRITE,  # Write ICS files to temp
                Capability.API_CALENDAR,       # (Future) Sync with Google Calendar
            ],
            
            # Resource limits (this is a light plugin)
            resource_limits=ResourceLimits(
                max_cpu_percent=25.0,
                max_memory_mb=128,
            ),
            
            homepage="https://github.com/yourusername/rosey-calendar-plugin",
            license="MIT",
        )
    
    async def on_start(self):
        """Initialize plugin"""
        logger.info("📅 Calendar plugin starting...")
        
        # Subscribe to messages (permission will be validated)
        await self.subscribe_to_events(['message', 'user.join'])
        
        # State
        self.meeting_discussions = {}  # Track threads discussing meetings
    
    async def handle_command(self, event: Event):
        """
        Handle calendar commands
        
        Commands:
            !calendar create - Generate ICS from thread context
            !calendar list - List upcoming events
        """
        data = event.data
        action = data.get("action", "create")
        
        if action == "create":
            await self.create_calendar_event(event)
        elif action == "list":
            await self.list_events(event)
        else:
            await self.publish_error(f"Unknown action: {action}", event.correlation_id)
    
    async def on_event(self, event: Event):
        """
        Listen to messages for meeting discussions
        
        Detects patterns like:
        - "Let's meet Thursday at 2pm"
        - "Meeting on 11/20 at 3:00 PM"
        - "Conference room A at noon"
        """
        if event.event_type != "message":
            return
        
        message = event.data.get("message", {}).get("text", "")
        
        # Simple meeting detection (real implementation would use NLP)
        if self._looks_like_meeting_discussion(message):
            channel = event.data.get("channel")
            
            if channel not in self.meeting_discussions:
                self.meeting_discussions[channel] = []
            
            self.meeting_discussions[channel].append({
                "text": message,
                "user": event.data.get("user", {}).get("username"),
                "timestamp": event.timestamp,
            })
            
            logger.info(f"Detected meeting discussion in {channel}")
    
    async def create_calendar_event(self, event: Event):
        """
        Generate ICS file from thread context
        
        This demonstrates:
        1. Checking capability before filesystem operation
        2. Generating file (ICS format)
        3. Sending response with attachment info
        """
        # Check we have filesystem permission
        if not self.has_capability(Capability.FILESYSTEM_WRITE):
            await self.publish_error(
                "Calendar plugin needs FILESYSTEM_WRITE capability to create ICS files",
                event.correlation_id
            )
            return
        
        # Extract meeting details from command context
        data = event.data
        channel = data.get("channel")
        
        # Get meeting discussion from this channel/thread
        discussion = self.meeting_discussions.get(channel, [])
        
        if not discussion:
            await self.publish_result({
                "message": "No meeting discussion detected in this thread. Please discuss meeting details first."
            }, event.correlation_id)
            return
        
        # Parse meeting details (simplified)
        meeting_info = self._parse_meeting_details(discussion)
        
        # Generate ICS file
        ics_content = self._generate_ics(meeting_info)
        
        # In real implementation, would write to temp file and upload
        # For now, just send text response
        await self.publish_result({
            "message": f"📅 Calendar Event Created!\n\n"
                      f"**{meeting_info['title']}**\n"
                      f"Date: {meeting_info['date']}\n"
                      f"Time: {meeting_info['time']}\n"
                      f"Location: {meeting_info['location']}\n\n"
                      f"(ICS file generation implemented in full version)",
            "meeting_info": meeting_info,
            # "attachment": "path/to/meeting.ics"  # Future
        }, event.correlation_id)
        
        logger.info(f"Created calendar event for {channel}")
    
    def _looks_like_meeting_discussion(self, text: str) -> bool:
        """Detect if message is about meeting planning"""
        keywords = [
            r'\bmeet\b', r'\bmeeting\b', r'\bconference\b',
            r'\bat \d+', r'\d+:\d+ (am|pm)',
            r'\bthursday\b', r'\bfriday\b', r'\bmonday\b',
        ]
        
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in keywords)
    
    def _parse_meeting_details(self, discussion: list) -> dict:
        """Parse meeting details from discussion (simplified)"""
        # Real implementation would use NLP, LLM, or structured parsing
        return {
            "title": "Team Meeting",
            "date": "2025-11-20",
            "time": "14:00",
            "location": "Conference Room A",
            "participants": [msg["user"] for msg in discussion],
        }
    
    def _generate_ics(self, meeting_info: dict) -> str:
        """Generate ICS file content"""
        # Simplified ICS format
        return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Rosey Calendar Plugin//EN
BEGIN:VEVENT
UID:{meeting_info['date']}-{meeting_info['time']}@rosey-bot
DTSTAMP:20251114T120000Z
DTSTART:{meeting_info['date'].replace('-', '')}T{meeting_info['time'].replace(':', '')}00
SUMMARY:{meeting_info['title']}
LOCATION:{meeting_info['location']}
DESCRIPTION:Generated by Rosey Calendar Plugin
END:VEVENT
END:VCALENDAR"""
    
    async def list_events(self, event: Event):
        """List upcoming events"""
        await self.publish_result({
            "message": "📅 Upcoming Events: (feature in development)"
        }, event.correlation_id)


if __name__ == "__main__":
    run_plugin(CalendarPlugin)
```

---

### Task 6b.5: Permission Enforcement in PluginProcess

**Update:** `bot/rosey/plugins/plugin_runner.py`

```python
"""
Add resource limit enforcement to PluginProcess
"""

# Add to PluginProcess class:

class PluginProcess:
    """
    Plugin process runner (UPDATED with resource enforcement)
    """
    
    def __init__(
        self,
        plugin_name: str,
        plugin_path: str,
        manifest: PluginManifest = None,  # NEW parameter
        **kwargs
    ):
        # ... existing init ...
        self.manifest = manifest
        self._resource_violations = []
    
    async def check_resource_limits(self) -> List[str]:
        """
        Check if plugin exceeds resource limits
        
        Returns:
            List of violations (empty if OK)
        """
        if not self.manifest:
            return []  # No limits if no manifest
        
        stats = self.get_stats()
        
        from bot.rosey.plugins.permission_validator import PermissionValidator
        validator = PermissionValidator(self.manifest)
        
        violations = validator.check_resource_limits(stats)
        
        if violations:
            logger.warning(f"Plugin '{self.plugin_name}' resource violations: {violations}")
            self._resource_violations.extend(violations)
        
        return violations
    
    async def enforce_limits(self):
        """
        Enforce resource limits
        
        If plugin exceeds limits, restart or terminate
        """
        violations = await self.check_resource_limits()
        
        if not violations:
            return
        
        # Policy: Restart on first violation, terminate on repeated violations
        violation_count = len(self._resource_violations)
        
        if violation_count >= 3:
            logger.error(
                f"Plugin '{self.plugin_name}' exceeded limits {violation_count} times. "
                "Terminating."
            )
            await self.stop()
        elif violation_count >= 1:
            logger.warning(
                f"Plugin '{self.plugin_name}' exceeded limits. Restarting."
            )
            await self.stop()
            await self.start()
```

---

## Configuration

### Plugin Manifest File (Alternative to Code)

**File:** `plugins/calendar/manifest.yaml`

```yaml
name: calendar
version: 1.0.0
description: Calendar event manager
author: Rosey Team

permissions:
  subjects:
    - pattern: rosey.events.message
      allow_subscribe: true
    
    - pattern: rosey.events.user.join
      allow_subscribe: true
    
    - pattern: rosey.platform.*.send.chat
      allow_publish: true
  
  capabilities:
    - filesystem.write
    - api.calendar

resource_limits:
  max_cpu_percent: 25.0
  max_memory_mb: 128
  max_uptime_hours: 24
  max_message_rate: 100

metadata:
  homepage: https://github.com/user/rosey-calendar
  repository: https://github.com/user/rosey-calendar
  license: MIT
```

---

## Testing

### Task 6b.6: Permission Tests

**File:** `tests/plugins/test_permissions.py`

```python
"""
Tests for plugin permission system
"""
import pytest
from bot.rosey.plugins.plugin_manifest import (
    PluginManifest,
    SubjectPermission,
    Capability,
    ResourceLimits
)
from bot.rosey.plugins.permission_validator import (
    PermissionValidator,
    PermissionDeniedError
)


def test_manifest_creation():
    """Test manifest creation"""
    manifest = PluginManifest(
        name="test",
        version="1.0.0",
        description="Test plugin",
        subject_permissions=[
            SubjectPermission("rosey.events.*", allow_subscribe=True)
        ],
        capabilities=[Capability.FILESYSTEM_WRITE]
    )
    
    assert manifest.name == "test"
    assert len(manifest.capabilities) == 1
    assert Capability.FILESYSTEM_WRITE in manifest.capabilities


def test_validator_allows_default_subjects():
    """Test validator allows default plugin subjects"""
    manifest = PluginManifest(
        name="test",
        version="1.0.0",
        description="Test"
    )
    
    validator = PermissionValidator(manifest)
    
    # Should allow own command subjects
    validator.validate_subscribe("rosey.commands.test.execute")
    validator.validate_publish("rosey.commands.test.result")
    validator.validate_publish("rosey.plugins.test.event")


def test_validator_denies_unauthorized_subscribe():
    """Test validator denies unauthorized subscriptions"""
    manifest = PluginManifest(
        name="test",
        version="1.0.0",
        description="Test"
    )
    
    validator = PermissionValidator(manifest)
    
    # Should deny subscription to events without permission
    with pytest.raises(PermissionDeniedError):
        validator.validate_subscribe("rosey.events.message")


def test_validator_allows_declared_permissions():
    """Test validator allows declared permissions"""
    manifest = PluginManifest(
        name="test",
        version="1.0.0",
        description="Test",
        subject_permissions=[
            SubjectPermission("rosey.events.message", allow_subscribe=True)
        ]
    )
    
    validator = PermissionValidator(manifest)
    
    # Should allow with permission
    validator.validate_subscribe("rosey.events.message")


def test_validator_checks_capabilities():
    """Test capability validation"""
    manifest = PluginManifest(
        name="test",
        version="1.0.0",
        description="Test",
        capabilities=[Capability.FILESYSTEM_WRITE]
    )
    
    validator = PermissionValidator(manifest)
    
    # Should allow declared capability
    validator.validate_capability(Capability.FILESYSTEM_WRITE)
    
    # Should deny undeclared capability
    with pytest.raises(PermissionDeniedError):
        validator.validate_capability(Capability.NETWORK_HTTP)


def test_resource_limit_checking():
    """Test resource limit validation"""
    manifest = PluginManifest(
        name="test",
        version="1.0.0",
        description="Test",
        resource_limits=ResourceLimits(
            max_cpu_percent=50.0,
            max_memory_mb=256
        )
    )
    
    validator = PermissionValidator(manifest)
    
    # Within limits
    stats = {"cpu_percent": 30.0, "memory_mb": 200, "uptime_seconds": 1000}
    violations = validator.check_resource_limits(stats)
    assert len(violations) == 0
    
    # Exceeds CPU limit
    stats = {"cpu_percent": 75.0, "memory_mb": 200, "uptime_seconds": 1000}
    violations = validator.check_resource_limits(stats)
    assert len(violations) == 1
    assert "CPU" in violations[0]
    
    # Exceeds memory limit
    stats = {"cpu_percent": 30.0, "memory_mb": 512, "uptime_seconds": 1000}
    violations = validator.check_resource_limits(stats)
    assert len(violations) == 1
    assert "Memory" in violations[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

## Documentation

**File:** `docs/plugins/PLUGIN-PERMISSIONS.md`

```markdown
# Plugin Permission System

## Overview

All plugins run with restricted permissions for security. Plugins must declare what they need in their manifest.

## Permission Types

### 1. NATS Subject Permissions

Control what events plugin can subscribe to and publish.

```python
subject_permissions=[
    SubjectPermission(
        pattern="rosey.events.message",
        allow_subscribe=True
    ),
]
```

**Default permissions** (always granted):
- Subscribe: `rosey.commands.{plugin_name}.execute`
- Publish: `rosey.commands.{plugin_name}.result`
- Publish: `rosey.commands.{plugin_name}.error`
- Publish: `rosey.plugins.{plugin_name}.*`

### 2. Capabilities

Opt-in permissions for special operations:

```python
capabilities=[
    Capability.FILESYSTEM_WRITE,  # Write files
    Capability.NETWORK_HTTP,       # Make HTTP requests
    Capability.API_CALENDAR,       # Access calendar API
]
```

**Available capabilities:**
- `FILESYSTEM_READ` - Read files
- `FILESYSTEM_WRITE` - Write files
- `FILESYSTEM_TEMP` - Write to temp directory only
- `NETWORK_HTTP` - Make HTTP requests
- `NETWORK_WEBSOCKET` - WebSocket connections
- `API_CALENDAR` - Calendar API access
- `API_EXTERNAL` - Generic external API
- `DATABASE_READ` - Read from plugin storage
- `DATABASE_WRITE` - Write to plugin storage
- `PLUGIN_BROADCAST` - Publish to other plugins
- `PLUGIN_LISTEN` - Subscribe to other plugins

### 3. Resource Limits

Prevent resource exhaustion:

```python
resource_limits=ResourceLimits(
    max_cpu_percent=50.0,    # Max 50% CPU
    max_memory_mb=256,       # Max 256MB RAM
    max_uptime_hours=24,     # Restart after 24h
    max_message_rate=100,    # Max 100 msg/sec
)
```

## Example Manifest

```python
def get_manifest(self) -> PluginManifest:
    return PluginManifest(
        name="calendar",
        version="1.0.0",
        description="Calendar event manager",
        author="Me",
        
        subject_permissions=[
            SubjectPermission("rosey.events.message", allow_subscribe=True),
        ],
        
        capabilities=[
            Capability.FILESYSTEM_WRITE,
            Capability.API_CALENDAR,
        ],
        
        resource_limits=ResourceLimits(
            max_cpu_percent=25.0,
            max_memory_mb=128,
        )
    )
```

## Using Permissions in Plugin Code

### Check capability before operation

```python
async def write_file(self, path: str, data: str):
    # Assert capability (raises if missing)
    self.require_capability(Capability.FILESYSTEM_WRITE)
    
    # ... write file ...

# Or check without raising
if self.has_capability(Capability.NETWORK_HTTP):
    await self.fetch_data()
```

### Subscribe to events

```python
async def on_start(self):
    # Permission checked automatically
    await self.subscribe_to_events(['message', 'user.join'])
```

## What Happens on Violation?

**Subject permission violation:**
- `PermissionDeniedError` raised immediately
- Plugin cannot subscribe/publish
- Error logged with helpful message

**Capability violation:**
- `PermissionDeniedError` raised when accessed
- Operation blocked

**Resource limit violation:**
- Warning logged on first violation
- Plugin restarted on repeated violations
- Plugin terminated after 3 violations

## Security Best Practices

1. **Request minimum permissions** - Only what you need
2. **Check capabilities** - Before attempting operations
3. **Handle denials gracefully** - Don't crash on permission errors
4. **Respect limits** - Optimize to stay within resource bounds
5. **Document needs** - Explain why each permission is needed
```

---

## Success Criteria

✅ PluginManifest class implemented  
✅ PermissionValidator enforcing NATS subjects  
✅ Capability system implemented  
✅ Resource limit checking functional  
✅ PluginInterface updated with validation  
✅ Example plugin (calendar) demonstrating permissions  
✅ Tests covering all permission types  
✅ Documentation complete  

---

## Time Breakdown

- Manifest & validator design: 1 hour
- PermissionValidator implementation: 1.5 hours
- PluginInterface integration: 45 minutes
- Example plugin: 45 minutes
- Testing: 30 minutes
- Documentation: 30 minutes

**Total: 5 hours**

---

## Next: Sortie 7 - Plugin Manager

With permissions in place, we can now build the Plugin Manager that:
- Loads plugins with their manifests
- Monitors resource usage
- Enforces limits
- Handles restarts
- Coordinates multiple plugins

---

## Security Notes

**Current Protection Level: Good**
- ✅ Process isolation (6a)
- ✅ NATS subject allowlists (6b)
- ✅ Resource limits (6b)
- ✅ Capability system (6b)

**Future Enhancements:**
- Network isolation (containers or firewall rules)
- Filesystem chroot/jail
- Audit logging of all permission checks
- Rate limiting per plugin
- Cryptographic signing of plugin code
