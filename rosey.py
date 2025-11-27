#!/usr/bin/env python3
"""
Rosey v1.0 - Plugin-First CyTube Bot Orchestrator

Clean slate architecture:
- 100-line orchestrator (THIS FILE - orchestration only)
- Core infrastructure (event_bus, plugin_manager, cytube_connector, router)
- Plugins (60+ files, all functionality)
- Common services (database, config)

This file does ONE thing: coordinate component startup and shutdown.
All business logic lives in plugins.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.event_bus import EventBus
from core.plugin_manager import PluginManager
from core.cytube_connector import CytubeConnector
from core.cytube_channel import CytubeChannel
from core.router import CommandRouter
from common.config import get_config
from common.database_service import DatabaseService


logger = logging.getLogger(__name__)


class Rosey:
    """
    Rosey v1.0 Bot Orchestrator
    
    Responsibilities:
    1. Initialize core infrastructure (NATS, database)
    2. Start components (connector, router, plugin manager)
    3. Coordinate graceful shutdown
    
    That's it. Everything else is in plugins or core modules.
    """
    
    def __init__(self, config_path: str = "config.json"):
        # Load config dict and bot params
        self.config_dict, self.bot_params = get_config(config_path)
        
        # Convert dict to object with attribute access for convenience
        from types import SimpleNamespace
        def dict_to_obj(d):
            if isinstance(d, dict):
                return SimpleNamespace(**{k: dict_to_obj(v) for k, v in d.items()})
            elif isinstance(d, list):
                return [dict_to_obj(item) for item in d]
            else:
                return d
        
        self.config = dict_to_obj(self.config_dict)
        self.event_bus: Optional[EventBus] = None
        self.database: Optional[DatabaseService] = None
        self.plugin_manager: Optional[PluginManager] = None
        self.cytube: Optional[CytubeConnector] = None
        self.router: Optional[CommandRouter] = None
        
    async def start(self):
        """Start all components in correct order"""
        try:
            # 1. Event Bus (NATS) - communication backbone
            logger.info("Starting Event Bus (NATS)...")
            self.event_bus = EventBus(self.config.nats_url)
            await self.event_bus.connect()
            
            # 2. Database Service (NATS-based)
            logger.info("Starting Database Service...")
            db_path = self.config_dict["database"].get("path", "rosey.db")
            self.database = DatabaseService(self.event_bus, db_path)
            await self.database.start()
            
            # 3. Plugin Manager (loads and runs plugins)
            logger.info("Starting Plugin Manager...")
            self.plugin_manager = PluginManager(self.event_bus)
            # TODO: Plugin manager lifecycle - Sprint 22 integration pending
            logger.info("Plugin Manager initialized (lifecycle methods not yet implemented)")
            
            # 4. Router (routes commands to plugins)
            logger.info("Starting Router...")
            self.router = CommandRouter(self.event_bus, self.plugin_manager)
            await self.router.start()
            
            # 5. CyTube Connector (platform bridge)
            logger.info("Starting CyTube Connector...")
            try:
                # Create CyTube channel from config
                cytube_channel = CytubeChannel(
                    domain=self.config_dict["domain"],
                    channel=self.config_dict["channel"],
                    username=self.config_dict.get("user", "RoseyBot"),
                    secure=self.config_dict.get("secure", True)
                )
                connected = await cytube_channel.connect()
                
                if connected:
                    # Create connector with channel instance
                    self.cytube = CytubeConnector(self.event_bus, cytube_channel)
                    await self.cytube.start()
                    logger.info(f"✅ Connected to CyTube channel: {self.config_dict['channel']}")
                else:
                    logger.warning("⚠️ CyTube connection failed - bot will run in offline mode")
            except Exception as e:
                logger.warning(f"⚠️ CyTube connection error: {e} - bot will run in offline mode")
                self.cytube = None
            
            logger.info("✅ Rosey v1.0 started successfully!")
            logger.info(f"Plugins loaded: {len(self.plugin_manager.list_plugins())}")
            
        except Exception as e:
            logger.error(f"Failed to start Rosey: {e}", exc_info=True)
            await self.stop()
            raise
            
    async def stop(self):
        """Stop all components in reverse order"""
        logger.info("Shutting down Rosey...")
        
        if self.cytube:
            await self.cytube.stop()
        if self.router:
            await self.router.stop()
        # Plugin manager doesn't have stop() method yet
        if self.database:
            await self.database.stop()
        if self.event_bus:
            await self.event_bus.disconnect()
            
        logger.info("✅ Rosey v1.0 stopped")


async def main():
    """Entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    rosey = Rosey()
    
    try:
        await rosey.start()
        # Run until interrupted
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await rosey.stop()


if __name__ == "__main__":
    asyncio.run(main())
