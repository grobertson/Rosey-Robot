"""
Simple CyTube WebSocket Channel Implementation

Provides basic CyTube channel connection using websockets library.
This is a minimal implementation to bridge the gap between Sprint 22 architecture
and the CytubeConnector that expects a channel object.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Callable, Optional
import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


class CytubeChannel:
    """
    Minimal CyTube WebSocket channel implementation.
    
    Connects to CyTube server and provides basic channel interface
    for CytubeConnector to consume.
    """
    
    def __init__(
        self,
        domain: str,
        channel: str,
        username: str,
        secure: bool = True
    ):
        """
        Initialize CyTube channel.
        
        Args:
            domain: CyTube server domain (e.g., "cytu.be")
            channel: Channel name to join
            username: Bot username
            secure: Use WSS (True) or WS (False)
        """
        self.domain = domain
        self.name = channel  # CytubeConnector expects .name attribute
        self.username = username
        self.secure = secure
        
        # Connection state
        self._ws: Optional[WebSocketClientProtocol] = None
        self._connected = False
        self._event_handlers: Dict[str, Callable] = {}
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> bool:
        """
        Connect to CyTube channel.
        
        Returns:
            True if connected successfully
        """
        if self._connected:
            logger.warning(f"Already connected to {self.name}")
            return True
        
        try:
            # Build WebSocket URL
            protocol = "wss" if self.secure else "ws"
            url = f"{protocol}://{self.domain}/socket.io/?EIO=3&transport=websocket"
            
            logger.info(f"Connecting to CyTube: {url}")
            self._ws = await websockets.connect(url)
            
            # Wait for initial connection packet
            msg = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
            logger.debug(f"Received initial packet: {msg}")
            
            # Send joinChannel packet
            join_packet = self._encode_packet("joinChannel", {
                "name": self.name
            })
            await self._ws.send(join_packet)
            
            # Send login packet
            login_packet = self._encode_packet("login", {
                "name": self.username
            })
            await self._ws.send(login_packet)
            
            self._connected = True
            self._running = True
            
            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            logger.info(f"Connected to CyTube channel: {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to CyTube: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from CyTube channel."""
        if not self._connected:
            return
        
        self._running = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            await self._ws.close()
            self._ws = None
        
        self._connected = False
        logger.info(f"Disconnected from CyTube channel: {self.name}")
    
    def on(self, event_type: str, handler: Callable) -> None:
        """
        Register event handler.
        
        Args:
            event_type: Event type to handle (e.g., "chatMsg", "addUser")
            handler: Async callback function
        """
        self._event_handlers[event_type] = handler
        logger.debug(f"Registered handler for event: {event_type}")
    
    async def send_chat(self, message: str) -> None:
        """
        Send chat message to channel.
        
        Args:
            message: Message text to send
        """
        if not self._connected or not self._ws:
            logger.error("Cannot send message: not connected")
            return
        
        packet = self._encode_packet("chatMsg", {
            "msg": message
        })
        await self._ws.send(packet)
        logger.debug(f"Sent chat message: {message}")
    
    async def _receive_loop(self) -> None:
        """Background loop to receive and process WebSocket messages."""
        while self._running and self._connected:
            try:
                msg = await self._ws.recv()
                await self._handle_message(msg)
                
            except asyncio.CancelledError:
                break
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket connection closed")
                self._connected = False
                break
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                await asyncio.sleep(1.0)
    
    async def _handle_message(self, raw_message: str) -> None:
        """
        Parse and handle incoming WebSocket message.
        
        Args:
            raw_message: Raw WebSocket message string
        """
        try:
            # Socket.IO packet format: <packet_type>[<data>]
            # We're looking for type 4 (MESSAGE) which contains JSON events
            if not raw_message:
                return
            
            # Parse packet type
            packet_type = raw_message[0]
            
            if packet_type == '4':  # MESSAGE packet
                # Extract JSON payload
                if len(raw_message) > 1:
                    # Socket.IO message format: 4<id>["event_name", data]
                    # Find the JSON array
                    json_start = raw_message.find('[')
                    if json_start != -1:
                        json_data = raw_message[json_start:]
                        event_array = json.loads(json_data)
                        
                        if len(event_array) >= 2:
                            event_type = event_array[0]
                            event_data = event_array[1]
                            
                            # Call registered handler if exists
                            if event_type in self._event_handlers:
                                handler = self._event_handlers[event_type]
                                await handler(event_data)
                            
                            logger.debug(f"Received event: {event_type}")
            
            elif packet_type == '2':  # PING
                # Respond with PONG
                await self._ws.send('3')
                logger.debug("Sent PONG")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            logger.debug(f"Raw message: {raw_message}")
    
    def _encode_packet(self, event_type: str, data: Dict[str, Any]) -> str:
        """
        Encode Socket.IO packet.
        
        Args:
            event_type: Event type name
            data: Event data dictionary
            
        Returns:
            Encoded Socket.IO packet string
        """
        # Socket.IO packet format: 42["event_name", data]
        event_array = [event_type, data]
        return f"42{json.dumps(event_array)}"
