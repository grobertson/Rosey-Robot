#!/usr/bin/env python3

import re
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import logging
import asyncio
from time import localtime, strftime

import markovify

from lib import Bot, MessageParser
from lib.error import CytubeError, SocketIOError

from common import Shell, get_config, configure_logger


class MarkovBot(Bot):
    HELP = [
        'commands:',
        '!help',
        '!settings',
        '!setorder <order>',
        '!setlearn <true|false>',
        '!settrigger <regexp>',
        '!echo <text>',
        '!markov [start]',
        '!rmarkov [end]'
    ]

    LINK = re.compile(r'\bhttps?://\S+', re.I)

    def __init__(self, markov_file, chat_logger, media_logger,
                 *args, order=None, learn=False, trigger=None, **kwargs):
        super().__init__(*args, **kwargs)
        name = re.escape(self.user.name)
        self.trigger_expr = re.compile(trigger or name, re.I)
        self.user_name_expr = re.compile(r'\b%s(:|\b)' % name, re.I)
        self.markov_file = markov_file
        self.markov_text = ""  # Store original text
        self.markov = self._load_markov()
        self.markov_order = order or 2
        self.learn_enabled = learn
        self.max_length = 200
        self.chat_parser = MessageParser()
        self.chat_logger = chat_logger
        self.media_logger = media_logger
        self.on(
            'chatMsg',
            self.parse_chat,
            self.log_chat,
            self.ignore,
            self.command,
            self.reply,
            self.learn
        )
        self.on(
            'pm',
            self.parse_chat,
            self.log_chat,
            self.ignore,
            self.reply,
            self.learn
        )
        self.on('setCurrent', self.log_media)

    def _load_markov(self):
        """Load markov model from file if it exists."""
        try:
            with open(self.markov_file, 'r', encoding='utf-8') as f:
                text = f.read().strip()
                if text:
                    self.markov_text = text
                    return markovify.Text(text, state_size=self.markov_order)
        except (FileNotFoundError, IOError):
            pass
        return None

    def _save_markov(self):
        """Save markov model text to file."""
        if self.markov_text:
            try:
                with open(self.markov_file, 'w', encoding='utf-8') as f:
                    f.write(self.markov_text)
            except IOError as e:
                self.logger.error("Failed to save markov file: %s", e)

    def normalize(self, msg):
        msg = self.user_name_expr.sub('', msg)
        msg = self.LINK.sub('', msg)
        return msg.strip()

    def parse_chat(self, _, data):
        msg = self.chat_parser.parse(data.get('msg', '&lt;no message&gt;'))
        data['msg'] = msg
        data['normalized_msg'] = self.normalize(msg)

    def log_chat(self, ev, data):
        time = data.get('time', 0)
        time = strftime('%d/%m/%Y %H:%m:%S', localtime(time // 1000))
        user = data.get('username', '<no username>')
        msg = data.get('msg', '<no message>')
        if ev == 'pm':
            to = data.get('to', '<no username>')
            self.chat_logger.info('[%s] %s -> %s: %s', time, user, to, msg)
        else:
            self.chat_logger.info('[%s] %s: %s', time, user, msg)

    def log_media(self, *_):
        current = self.channel.playlist.current
        if current is not None:
            self.media_logger.info(
                '%s: %s "%s"',
                current.username, current.link.url, current.title
            )

    def ignore(self, _, data):
        if self.user == data['username']:
            self.logger.info('ignore self')
            return True
        if data['username'] == '[server]':
            self.logger.info('ignore server')
            return True
        if self.user.rank < 0:
            self.logger.info('ignore history')
            return True
        return False

    async def _reply(self, ev, username, msg):
        if ev == 'pm':
            await self.pm(username, msg)
        else:
            await self.chat('%s: %s' % (username, msg))

    async def reply(self, ev, data):
        msg = data['msg']
        if ev != 'pm' and not self.trigger_expr.search(msg):
            return
        msg = data['normalized_msg']
        self.logger.info('reply %r %s', msg, data)

        if self.markov:
            generated = self.markov.make_sentence(max_overlap_ratio=0.7, tries=100)
            if generated:
                msg = generated[:self.max_length]
            else:
                msg = "I don't have enough data to generate a response."
        else:
            msg = "I need to learn some text first."

        await self._reply(ev, data['username'], msg)

    async def learn(self, _, data):
        if not self.learn_enabled:
            return
        msg = data['normalized_msg']
        if msg:
            self.logger.info('learn %s', msg)
            # Combine with existing text and retrain
            if self.markov_text:
                combined_text = self.markov_text + "\n" + msg
            else:
                combined_text = msg
            self.markov_text = combined_text
            self.markov = markovify.Text(combined_text, state_size=self.markov_order)
            self._save_markov()

    async def command(self, _, data):
        msg = data['msg'].strip()
        if not msg.startswith('!'):
            return
        msg = msg.split(None, 1)
        if not msg:
            return

        data['cmd'] = msg[0][1:]
        if len(msg) == 1:
            data['msg'] = ''
        else:
            data['msg'] = msg[1]

        cmd = 'cmd_%s' % data['cmd']
        try:
            handler = getattr(self, cmd)
        except AttributeError:
            await self.chat(
                '%s: invalid command "%s"'
                % (data['username'], data['cmd'])
            )
            return True

        if asyncio.iscoroutinefunction(handler):
            await handler(data)
        else:
            handler(data)

        return True

    async def cmd_echo(self, data):
        msg = data['msg']
        if not msg:
            msg = '%s: usage: !echo <text>' % data['username']
        await self.chat(msg)

    async def cmd_setorder(self, data):
        msg = data['msg']
        if not msg:
            msg = '%s: usage: !setorder <order>' % data['username']
        try:
            order = int(msg)
            if order < 1 or order > 5:
                raise ValueError('order must be between 1 and 5')
            msg = '%s: order: %s -> %s' % (
                data['username'], self.markov_order, order
            )
            self.markov_order = order
            # Retrain model with new order if we have text
            if self.markov_text:
                self.markov = markovify.Text(self.markov_text, state_size=self.markov_order)
        except ValueError as ex:
            msg = '%s: %r' % (data['username'], ex)
        await self.chat(msg)

    async def cmd_setlearn(self, data):
        msg = data['msg'].lower()
        if msg in ('true', 'false'):
            learn = msg == 'true'
            msg = '%s: learn: %s -> %s' % (
                data['username'], self.learn_enabled, learn
            )
            self.learn_enabled = learn
        else:
            msg = '%s: usage: !setlearn <true|false>' % data['username']
        await self.chat(msg)

    async def cmd_settrigger(self, data):
        msg = data['msg']
        if not msg:
            msg = '%s: usage: !settrigger <regexp>' % data['username']
        else:
            try:
                trigger = re.compile(msg, re.I)
                msg = '%s: trigger: %s -> %s' % (
                    data['username'],
                    self.trigger_expr.pattern,
                    trigger.pattern
                )
                self.trigger_expr = trigger
            except re.error as ex:
                msg = '%s: %r' % (data['username'], ex)
        await self.chat(msg)

    async def cmd_settings(self, data):
        msg = '%s: order=%s learn=%s trigger=%s' % (
            data['username'],
            self.markov_order,
            self.learn_enabled,
            self.trigger_expr
        )
        await self.chat(msg)

    async def cmd_help(self, _):
        for msg in self.HELP:
            await self.chat(msg)
            await asyncio.sleep(0.2)

    async def _cmd_markov(self, data):
        msg = data['msg']
        if self.markov:
            if msg:
                # Try to generate sentence starting with the given text
                generated = self.markov.make_sentence_with_start(msg, strict=False, tries=100)
                if not generated:
                    generated = self.markov.make_sentence(tries=100)
            else:
                generated = self.markov.make_sentence(tries=100)

            if generated:
                msg = generated[:self.max_length]
            else:
                msg = "I couldn't generate a response."
        else:
            msg = "I need to learn some text first."

        await self.chat('%s: %s' % (data['username'], msg))

    async def cmd_markov(self, data):
        await self._cmd_markov(data)

    async def cmd_rmarkov(self, data):
        await self._cmd_markov(data)


async def run_bot():
    """Run the bot with proper async handling"""
    conf, kwargs = get_config()
    chat_logger = logging.getLogger('chat')
    media_logger = logging.getLogger('media')

    configure_logger(
        chat_logger,
        log_file=conf.get('chat_log_file', None),
        log_format='%(message)s',
        log_level=logging.INFO
    )
    configure_logger(
        media_logger,
        log_file=conf.get('media_log_file', None),
        log_format='[%(asctime).19s] %(message)s',
        log_level=logging.INFO
    )

    bot = MarkovBot(
        conf['markov'], chat_logger, media_logger,
        order=conf.get('order', None),
        learn=conf.get('learn', False),
        trigger=conf.get('trigger', None),
        **kwargs
    )
    shell = Shell(conf.get('shell', None), bot)
    await shell.start()

    try:
        await bot.run()
    except (CytubeError, SocketIOError) as ex:
        print(repr(ex), file=sys.stderr)
    except asyncio.CancelledError:
        pass
    finally:
        bot._save_markov()
        shell.close()


def main():
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        return 0

    return 1


if __name__ == '__main__':
    sys.exit(main())
