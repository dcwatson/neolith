from neolith import settings
from neolith.protocol import PostChat, ProtocolError, Sendable, Session, Transaction

from .constants import ERR, RPL

import asyncio
import base64
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
                # TODO: check authentication for non-login-related commands (PASS, USER, NICK, CAP, etc)
                asyncio.ensure_future(handler(*params, prefix=prefix))
            else:
                self.write(ERR.UNKNOWNCOMMAND, self.nickname or '*', cmd, 'Unknown command')
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
            if packet.user.ident != self.ident:
                self.write('PRIVMSG', channel.irc_name, packet.chat, prefix=packet.user)
        elif packet.ident == 'channel.joined':
            channel = self.server.channels[packet.channel]
            self.write('JOIN', channel.irc_name, prefix=packet.user)
        elif packet.ident == 'channel.left':
            channel = self.server.channels[packet.channel]
            self.write('PART', channel.irc_name, prefix=packet.user)

    async def check_login(self, sasl=False):
        if self.authenticated:
            return
        if self.username and self.nickname and not self.password:
            self.write('NOTICE', 'AUTH', '*** You are not logged in, please use PASS or AUTHENTICATE')
            return
        from neolith.models import Account
        if self.username and self.password and self.nickname:
            self.account = await Account.query(username=self.username).get()
            if self.account is None or self.account.password != self.account.password_spec.generate(self.password):
                raise ProtocolError('Login failed.')
            if sasl:
                self.write(RPL.LOGGEDIN, self.nickname, str(self), self.username,
                           'You are logged in as {}'.format(self.username))
                self.write(RPL.SASLSUCCESS, self.nickname, 'SASL authentication successful')
            await self.server.authenticate(self)
            self.write(RPL.WELCOME, self.nickname,
                       'Welcome to {}! The public chat room for this server is #{}'.format(
                           settings.SERVER_NAME, settings.PUBLIC_CHANNEL))

    async def handle_PING(self, *params, prefix=None):
        self.write('PONG', settings.SERVER_NAME, ' '.join(params))

    async def handle_CAP(self, *params, prefix=None):
        if params[0].upper() == 'LS':
            self.write('CAP', self.nickname or '*', 'LS', ':sasl')
        elif params[0].upper() == 'REQ':
            reqs = params[1].split()
            if 'sasl' in reqs:
                self.write('CAP', self.nickname or '*', 'ACK', ':sasl')

    async def handle_AUTHENTICATE(self, *params, prefix=None):
        if params[0] == 'PLAIN':
            self.write('AUTHENTICATE', '+')
        else:
            ident, auth, password = base64.b64decode(params[0]).split(b'\x00')
            self.username = ident.decode('utf-8')
            self.password = password.decode('utf-8')
            await self.check_login(sasl=True)

    async def handle_PASS(self, *params, prefix=None):
        self.password = params[0]
        await self.check_login()

    async def handle_USER(self, *params, prefix=None):
        self.username = params[0]
        # TODO: realname = params[3]
        await self.check_login()

    async def handle_NICK(self, *params, prefix=None):
        if not params or params[0] == self.nickname:
            return
        if self.server.get(nickname=params[0], authenticated=True):
            self.write(ERR.NICKNAMEINUSE, '*', 'Nickname is already in use.')
        else:
            self.nickname = params[0]
            if self.authenticated:
                # TODO: send user.modified
                pass
            else:
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
