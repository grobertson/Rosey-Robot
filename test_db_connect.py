#!/usr/bin/env python3
"""Test database connection with empty database"""
import asyncio
from common.database import BotDatabase

async def main():
    db = BotDatabase('test_bot_data.db')
    await db.connect()
    print('✓ Database connection successful with empty database')
    await db.close()

if __name__ == '__main__':
    asyncio.run(main())
