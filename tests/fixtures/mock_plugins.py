"""
Mock plugins for testing
"""
import asyncio
from typing import Dict, Any, Optional


class MockPlugin:
    """Base mock plugin"""
    
    def __init__(self, name: str, event_bus=None):
        self.name = name
        self.event_bus = event_bus
        self.is_running = False
        self.received_events = []
        self.sent_responses = []
    
    async def start(self):
        """Start plugin"""
        self.is_running = True
        
        if self.event_bus:
            await self.event_bus.subscribe(
                f"rosey.commands.{self.name}.>",
                self.handle_command
            )
    
    async def stop(self):
        """Stop plugin"""
        self.is_running = False
    
    async def handle_command(self, msg):
        """Handle command message"""
        import json
        
        data = json.loads(msg.data.decode())
        self.received_events.append(data)
        
        # Echo response
        response = {
            "status": "success",
            "message": f"Handled by {self.name}"
        }
        
        self.sent_responses.append(response)
        
        # Send response if reply subject provided
        if msg.reply:
            await self.event_bus.publish(
                msg.reply,
                json.dumps(response).encode()
            )


class MockEchoPlugin(MockPlugin):
    """Mock echo plugin"""
    
    def __init__(self, event_bus=None):
        super().__init__("echo", event_bus)
    
    async def handle_command(self, msg):
        """Echo back the message"""
        import json
        
        data = json.loads(msg.data.decode())
        self.received_events.append(data)
        
        # Extract message to echo
        message = data.get("data", {}).get("message", "")
        
        response = {
            "status": "success",
            "message": f"Echo: {message}"
        }
        
        self.sent_responses.append(response)
        
        if msg.reply:
            await self.event_bus.publish(
                msg.reply,
                json.dumps(response).encode()
            )


class MockTriviaPlugin(MockPlugin):
    """Mock trivia plugin"""
    
    def __init__(self, event_bus=None):
        super().__init__("trivia", event_bus)
        self.game_active = False
        self.current_question = None
    
    async def handle_command(self, msg):
        """Handle trivia commands"""
        import json
        
        data = json.loads(msg.data.decode())
        self.received_events.append(data)
        
        action = data.get("data", {}).get("action", "")
        
        if action == "start":
            self.game_active = True
            response = {
                "status": "success",
                "message": "Trivia game started!"
            }
        elif action == "answer":
            answer = data.get("data", {}).get("args", [""])[0]
            response = {
                "status": "success",
                "message": f"Answer received: {answer}"
            }
        else:
            response = {
                "status": "error",
                "message": f"Unknown action: {action}"
            }
        
        self.sent_responses.append(response)
        
        if msg.reply:
            await self.event_bus.publish(
                msg.reply,
                json.dumps(response).encode()
            )


class MockCrashPlugin(MockPlugin):
    """Mock plugin that crashes on command"""
    
    def __init__(self, event_bus=None):
        super().__init__("crash", event_bus)
    
    async def handle_command(self, msg):
        """Crash if commanded"""
        import json
        
        data = json.loads(msg.data.decode())
        self.received_events.append(data)
        
        action = data.get("data", {}).get("action", "")
        
        if action == "crash":
            raise RuntimeError("Intentional crash for testing")
        
        response = {
            "status": "success",
            "message": "Still alive"
        }
        
        self.sent_responses.append(response)
        
        if msg.reply:
            await self.event_bus.publish(
                msg.reply,
                json.dumps(response).encode()
            )
