from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect
import dorm
import uvicorn

from neolith import settings
from neolith.irc import IRCSession
from neolith.models import Account
from neolith.protocol import (
    Channel, ChannelJoin, ChannelLeave, ClientPacket, ProtocolError, Sendable, Session, Transaction, UserJoined,
    UserLeft)
from neolith.web import client, docs, signup

import asyncio
import binascii
import json
import os
import struct


class Channels:

    def __init__(self):
        self.channels = {}

    def __contains__(self, key: str):
        return key in self.channels

    def __getitem__(self, key: str):
        if key not in self.channels:
            raise ProtocolError('No such channel: "{}"'.format(key))
        return self.channels[key]

    def __iter__(self):
        return iter(self.channels.values())

    def add(self, channel):
        return self.channels.setdefault(channel.name, channel)


class NeolithServer:

    def __init__(self):
        self.loop = None
        self.server = None
        self.irc = None
        self.sessions = {}
        self.channels = Channels()
        self.secret_key = os.urandom(32)
        self.name = settings.SERVER_NAME
        if settings.PUBLIC_CHANNEL:
            self.channels.add(Channel(name=settings.PUBLIC_CHANNEL, topic='', protected=True, encrypted=False))
        self.web = Starlette(debug=True)
        self.web.add_event_handler('startup', self.startup)
        self.web.add_event_handler('shutdown', self.shutdown)
        self.web.add_route('/api', self.web_handler, methods=['GET', 'POST'])
        self.web.add_websocket_route('/ws', self.websocket_handler)
        # Server static files
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        self.web.mount('/static', StaticFiles(directory=static_dir))
        if settings.ENABLE_WEB_CLIENT:
            self.web.add_route('/', client, methods=['GET'])
        if settings.ENABLE_DOCS:
            self.web.add_route('/docs', docs, methods=['GET'])
        if settings.ENABLE_SIGNUP:
            self.web.add_route('/signup', signup, methods=['GET', 'POST'])

    async def startup(self):
        dorm.setup(settings.DATABASE, models=[Account])
        print('Starting binary protocol server on {}:{}'.format(settings.SOCKET_BIND, settings.SOCKET_PORT))
        # Careful not to use the event loop until after uvicorn starts it, since it may swap in uvloop.
        self.loop = asyncio.get_event_loop()
        self.server = await self.loop.create_server(lambda: SocketSession(self), settings.SOCKET_BIND,
            settings.SOCKET_PORT)
        if settings.ENABLE_IRC:
            print('Starting IRC server on {}:{}'.format(settings.IRC_BIND, settings.IRC_PORT))
            self.irc = await self.loop.create_server(lambda: IRCSession(self), settings.IRC_BIND, settings.IRC_PORT)

    async def shutdown(self):
        print('Stopping binary protocol server')
        self.server.close()
        if self.irc:
            self.irc.close()

    async def web_handler(self, request):
        session_token = request.headers.get('x-neolith-session')
        session = self.get(token=session_token, default=WebSession())
        if request.method == 'GET':
            return JSONResponse([tx.to_dict() for tx in await session.events()])
        elif request.method == 'POST':
            session.hostname = request.client.host
            if not session.ident:
                await self.connected(session)
            tx = Transaction(await request.json())
            response = await self.handle(session, tx, send=False)
            return JSONResponse(response.to_dict())
        else:
            return JSONResponse({'error': 'Invalid HTTP method.'}, status_code=405)

    async def websocket_handler(self, websocket, **kwargs):
        await websocket.accept()

        session = WebSocketSession(websocket)
        session.hostname = websocket.client.host

        await self.connected(session)

        try:
            while True:
                tx = Transaction(await websocket.receive_json())
                await self.handle(session, tx)
        except WebSocketDisconnect:
            print('websocket disconnected')
        finally:
            await self.disconnected(session)

    async def handle(self, session, transaction, send=True):
        print(session, '-->', transaction.to_dict())
        response = transaction.response()
        for packet in transaction.packets:
            assert isinstance(packet, ClientPacket)
            try:
                if packet.requires_auth and not session.authenticated:
                    raise ProtocolError('This request requires authentication.')
                response.add(await packet.handle(self, session))
            except ProtocolError as e:
                response.error = str(e)
        if send and not response.empty:
            await session.send(response)
        return response

    async def connected(self, session):
        print('New connection - {}'.format(session))
        session.ident = binascii.hexlify(os.urandom(16)).decode('ascii')
        session.token = binascii.hexlify(os.urandom(16)).decode('ascii')
        self.sessions[session.ident] = session

    async def disconnected(self, session):
        if session.authenticated:
            session.authenticated = False
            for channel in self.channels:
                if session in channel.sessions:
                    channel.remove(session)
                    await channel.send(ChannelLeave(channel=channel.name, user=session))
            await self.broadcast(UserLeft(user=session))
        if session.ident in self.sessions:
            del self.sessions[session.ident]

    def start(self):
        uvicorn.run(self.web, host=settings.WEB_BIND, port=settings.WEB_PORT)

    async def broadcast(self, message):
        for session in self.sessions.values():
            if session.authenticated:
                await session.send(message)

    async def authenticate(self, session):
        if session.authenticated:
            raise ProtocolError('Session is already authenticated.')
        if self.get(nickname=session.nickname, authenticated=True):
            raise ProtocolError('This nickname is already in use.')
        # XXX: where should this go? maybe a new task to be executed next time through the loop?
        await self.broadcast(UserJoined(user=session))
        if settings.PUBLIC_CHANNEL and settings.AUTO_JOIN:
            channel = self.channels[settings.PUBLIC_CHANNEL]
            channel.add(session)
            await channel.send(ChannelJoin(channel=settings.PUBLIC_CHANNEL, user=session))
        # Authenticate the session after sending the joins, so we don't send joins before the login response.
        print('Authenticated {}'.format(session))
        session.authenticated = True
        return session.ident

    def find(self, **kwargs):
        for session in self.sessions.values():
            match = True
            for field, value in kwargs.items():
                if getattr(session, field) != value:
                    match = False
            if match:
                yield session

    def get(self, **kwargs):
        default = kwargs.pop('default', None)
        for session in self.find(**kwargs):
            return session
        return default


class SocketSession (asyncio.Protocol, Session):

    def __init__(self, delegate):
        self.delegate = delegate
        self.buffered = b''
        self.transport = None
        self.address = None
        self.port = None

    def connection_made(self, transport: asyncio.Transport):
        self.transport = transport
        self.address, self.port = self.transport.get_extra_info('peername')
        self.hostname = self.address  # TODO: look up hostname from address?
        if hasattr(self.delegate, 'connected'):
            asyncio.ensure_future(self.delegate.connected(self))

    def connection_lost(self, exc):
        if hasattr(self.delegate, 'disconnected'):
            asyncio.ensure_future(self.delegate.disconnected(self))

    def data_received(self, data: bytes):
        self.buffered += data
        done = len(self.buffered) < 4
        while not done:
            size = struct.unpack('!L', self.buffered[:4])[0]
            total = 4 + size
            if len(self.buffered) >= total:
                json_data = json.loads(self.buffered[4:total])
                tx = Transaction(data=json_data)
                asyncio.ensure_future(self.delegate.handle(self, tx))
                self.buffered = self.buffered[total:]
                done = len(self.buffered) < 4
            else:
                done = True

    async def send(self, data: Sendable):
        print(self, '<--', data.to_dict())
        buf = json.dumps(data.to_dict()).encode('utf-8')
        self.transport.write(struct.pack('!L', len(buf)) + buf)


class WebSocketSession (Session):

    def __init__(self, websocket):
        self.websocket = websocket

    async def send(self, data: Sendable):
        print(self, '<--', data.to_dict())
        await self.websocket.send_json(data.to_dict())


class WebSession (Session):

    def __init__(self):
        self.queue = asyncio.Queue()

    async def send(self, data: Sendable):
        print(self, '<--', data.to_dict())
        await self.queue.put(data)

    async def events(self, timeout=10.0):
        if self.queue.empty():
            # If there are no pending events, allow for long-polling until one comes in.
            try:
                return [await asyncio.wait_for(self.queue.get(), timeout=timeout)]
            except asyncio.TimeoutError:
                return []
        else:
            return [self.queue.get_nowait() for i in range(self.queue.qsize())]


if __name__ == '__main__':
    NeolithServer().start()
