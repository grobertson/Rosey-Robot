#!/usr/bin/env python3

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio

from lib import Bot, MessageParser
from lib.error import CytubeError, SocketIOError

from common import Shell, get_config


class EchoBot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.msg_parser = MessageParser()
        self.on('chatMsg', self.echo)
        self.on('pm', self.echo)

    async def echo(self, event, data):
        username = data['username']
        if username == self.user.name or self.user.rank < 0:
            return
        msg = self.msg_parser.parse(data['msg'])
        if event == 'pm':
            await self.pm(data['username'], msg)
        elif msg.startswith(self.user.name):
            await self.chat(msg.replace(self.user.name, username, 1))


async def run_bot():
    """Run the bot with proper async handling"""
    conf, kwargs = get_config()

    bot = EchoBot(**kwargs)
    shell = Shell(conf.get('shell', None), bot)
    await shell.start()

    try:
        await bot.run()
    except (CytubeError, SocketIOError) as ex:
        print(repr(ex), file=sys.stderr)
    except asyncio.CancelledError:
        pass
    finally:
        shell.close()


def main():
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        return 0

    return 1


if __name__ == '__main__':
    sys.exit(main())
