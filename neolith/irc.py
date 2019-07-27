from neolith import settings
from neolith.protocol import PostChat, ProtocolError, Sendable, Session, Transaction

from .constants import RPL

import asyncio
import logging


def escape(text):
    # TODO: escape stuff
    if ' ' in text:
        return ':' + text
    return text


class IRCSession (asyncio.Protocol, Session):

    # Mostly for the server to associate a HLUser with this connection.
    user = None
    password = None

    def __init__(self, server):
        self.server = server
        self.transport = None
        self.address = None
        self.port = None
        self.buffer = b''

    def connection_made(self, transport):
        self.transport = transport
        self.address, self.port = transport.get_extra_info('peername')
        self.hostname = self.address
        if hasattr(self.server, 'connected'):
            asyncio.ensure_future(self.server.connected(self))

    def connection_lost(self, exc):
        if hasattr(self.server, 'disconnected'):
            asyncio.ensure_future(self.server.disconnected(self))

    def data_received(self, data):
        self.buffer += data
        *lines, self.buffer = self.buffer.split(b'\r\n')
        for line in lines:
            parts = line.decode('utf-8').split(':', 2)
            if parts[0]:
                prefix = None
                cmd, *params = parts[0].strip().split(' ')
                params.extend(parts[1:])
            else:
                prefix, cmd, *params = parts[1].strip().split(' ')
                params.extend(parts[2:])
            handler = getattr(self, 'handle_{}'.format(cmd.upper()), None)
            if handler:
                asyncio.ensure_future(handler(*params, prefix=prefix))
            else:
                logging.debug('Unknown IRC command "%s" with params: %s', cmd, params)

    def write(self, code, *params, prefix=None):
        start = ':{}'.format(prefix or settings.SERVER_NAME)
        line = '{} {} {}\r\n'.format(start, code, ' '.join(escape(p) for p in params))
        self.transport.write(line.encode('utf-8'))

    async def send(self, data: Sendable):
        print(self, '(IRC) <--', data.to_dict())
        for packet in data:
            await self.rewrite(packet)

    async def rewrite(self, packet):
        if packet.ident == 'channel.posted' and packet.chat:
            channel = self.server.channels[packet.channel]
            self.write('PRIVMSG', channel.irc_name, packet.chat, prefix=packet.user)
        elif packet.ident == 'channel.joined':
            channel = self.server.channels[packet.channel]
            self.write('JOIN', channel.irc_name, prefix=packet.user)
        elif packet.ident == 'channel.left':
            channel = self.server.channels[packet.channel]
            self.write('PART', channel.irc_name, prefix=packet.user)

    async def check_login(self):
        if self.authenticated:
            return
        from neolith.models import Account
        if self.username and self.password and self.nickname:
            self.account = await Account.query(username=self.username).get()
            if self.account is None or self.account.password != self.account.password_spec.generate(self.password):
                raise ProtocolError('Login failed.')
            await self.server.authenticate(self)
            self.write(RPL.WELCOME, self.nickname,
                       'The public chat room for this server is #{}'.format(settings.PUBLIC_CHANNEL))

    async def handle_PING(self, *params, prefix=None):
        self.write('PONG', settings.SERVER_NAME, ' '.join(params))

    async def handle_PASS(self, *params, prefix=None):
        self.password = params[0]
        await self.check_login()

    async def handle_USER(self, *params, prefix=None):
        self.username = params[0]
        # TODO: realname = params[3]
        await self.check_login()

    async def handle_NICK(self, *params, prefix=None):
        # TODO: check nickname
        self.nickname = params[0]
        await self.check_login()

    async def handle_JOIN(self, *params, prefix=None):
        channel = self.server.channels[params[0][1:]]
        # TODO: create if it doesn't exist, and the user has permission
        if not channel.add(self):
            return
        self.write('JOIN', channel.irc_name, prefix=self)
        if channel.topic:
            self.write(RPL.TOPIC, self.nickname, channel.irc_name, channel.topic)
        else:
            self.write(RPL.NOTOPIC, self.nickname, channel.irc_name)
        # Channels: = for public, * for private, @ for secret
        # Users: @ for ops, + for voiced
        self.write(RPL.NAMREPLY, self.nickname, '=', channel.irc_name, ' '.join(
            s.nickname for s in channel.sessions if s.authenticated))
        self.write(RPL.ENDOFNAMES, self.nickname, channel.irc_name, 'End of NAMES list')

    async def handle_PRIVMSG(self, *params, prefix=None):
        if params[0].startswith('#'):
            channel = self.server.channels[params[0][1:]]
            tx = Transaction(packets=[
                PostChat(channel=channel.name, chat=params[1], emote=False)
            ])
            await self.server.handle(self, tx)

    async def handle_MODE(self, *params, prefix=None):
        pass

    async def handle_WHO(self, *params, prefix=None):
        if params and params[0].startswith('#'):
            channel = self.server.channels[params[0][1:]]
            for user in channel.sessions:
                if user.authenticated:
                    self.write(RPL.WHOREPLY, self.nickname, channel.irc_name, user.username,
                               user.hostname, settings.SERVER_NAME, user.nickname, 'H', '0 Real Name')
            self.write(RPL.ENDOFWHO, self.nickname, channel.irc_name, 'End of WHO list')

    async def handle_QUIT(self, *params, prefix=None):
        self.write('ERROR', 'Bye for now!')
        self.transport.close()
