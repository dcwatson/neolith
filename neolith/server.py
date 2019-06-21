from starlette.applications import Starlette
from starlette.responses import JSONResponse
import uvicorn

from neolith import settings
from neolith.protocol import Channel, ClientPacket, Packet, ProtocolError, Session

import asyncio
import binascii
import os
import struct


class Channels:

    def __init__(self):
        self.channels = {}

    def __getitem__(self, key: str):
        if key not in self.channels:
            raise ProtocolError('Invalid channel.')
        return self.channels[key]

    def add(self, name, **kwargs):
        return self.channels.setdefault(name, Channel(name, **kwargs))


class NeolithServer:

    def __init__(self):
        self.loop = None
        self.server = None
        self.sessions = {}
        self.channels = Channels()
        if settings.PUBLIC_CHANNEL:
            # XXX: public channel encryption probably not necessary, just testing
            self.channels.add(settings.PUBLIC_CHANNEL, protected=True, encrypted=True)
        self.web = Starlette(debug=True)
        self.web.add_event_handler('startup', self.startup)
        self.web.add_event_handler('shutdown', self.shutdown)
        self.web.add_route('/api/events', self.events_handler, methods=['GET', 'POST'])
        self.web.add_route('/api/{ident:path}', self.api_handler, methods=['GET', 'POST'])

    async def startup(self):
        print('Starting binary protocol server on {}:{}'.format(settings.SOCKET_BIND, settings.SOCKET_PORT))
        # Careful not to use the event loop until after uvicorn starts it, since it may swap in uvloop.
        self.loop = asyncio.get_event_loop()
        self.server = await self.loop.create_server(lambda: SocketSession(self), settings.SOCKET_BIND, settings.SOCKET_PORT)

    async def shutdown(self):
        print('Stopping binary protocol server')
        self.server.close()

    async def api_handler(self, request):
        ident = request.path_params['ident'].rstrip('/').replace('/', '.')
        packet_class = Packet.find(ident)
        if packet_class is None:
            return JSONResponse({'error': 'Invalid packet type: "{}"'.format(ident)}, status_code=404)
        if request.method == 'GET':
            return JSONResponse(packet_class.describe())
        elif request.method == 'POST':
            session_token = request.headers.get('x-neolith-session')
            session = self.get(token=session_token, default=WebSession())
            session.hostname = request.client.host
            packet = packet_class.unpack(await request.json())
            response = await self.handle(session, packet, send=False)
            if response:
                return JSONResponse({
                    response.ident: response.prepare(),
                })
            else:
                return JSONResponse({})
        else:
            return JSONResponse({'error': 'Invalid HTTP method.'}, status_code=405)

    async def events_handler(self, request):
        session_token = request.headers.get('x-neolith-session')
        session = self.get(token=session_token, default=WebSession())
        packets = [{p.ident: p.prepare()} for p in session.queue]
        session.queue = []
        return JSONResponse(packets)

    async def handle(self, session, packet, send=True):
        assert isinstance(packet, ClientPacket)
        if packet.requires_auth and not session.authenticated:
            raise ProtocolError('This request requires authentication.')
        response = await packet.handle(self, session)
        if response and send:
            session.send(response)
        return response

    def start(self):
        uvicorn.run(self.web, host=settings.WEB_BIND, port=settings.WEB_PORT)

    def broadcast(self, message):
        for session in self.sessions.values():
            if session.authenticated:
                session.send(message)

    def authenticate(self, session):
        if session.ident in self.sessions:
            raise ProtocolError('Session is already authenticated.')
        if self.get(nickname=session.nickname):
            raise ProtocolError('This nickname is already in use.')
        session.authenticated = True
        session.ident = binascii.hexlify(os.urandom(16)).decode('ascii')
        session.token = binascii.hexlify(os.urandom(16)).decode('ascii')
        self.sessions[session.ident] = session
        print('Authenticated {}'.format(session))
        # XXX: where should this go?
        if settings.PUBLIC_CHANNEL:
            self.channels[settings.PUBLIC_CHANNEL].add(session)
        return session.ident

    def connected(self, session):
        pass

    def disconnected(self, session):
        session.authenticated = False
        if session.ident in self.sessions:
            del self.sessions[session.ident]

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

    def __init__(self, server):
        self.server = server
        self.buffered = b''
        self.transport = None
        self.address = None
        self.port = None

    def connection_made(self, transport: asyncio.Transport):
        self.transport = transport
        self.address, self.port = self.transport.get_extra_info('peername')
        self.hostname = self.address  # TODO: look up hostname from address?
        self.server.connected(self)

    def connection_lost(self, exc):
        self.server.disconnected(self)

    def data_received(self, data: bytes):
        self.buffered += data
        done = len(self.buffered) < 4
        while not done:
            size = struct.unpack('!L', self.buffered[:4])[0]
            total = 4 + size
            if len(self.buffered) >= total:
                for packet in Packet.deserialize(self.buffered[4:total]):
                    asyncio.ensure_future(self.server.handle(self, packet))
                self.buffered = self.buffered[total:]
                done = len(self.buffered) < 4
            else:
                done = True

    def send(self, packet: Packet):
        buf = packet.serialize()
        self.transport.write(struct.pack('!L', len(buf)) + buf)


class WebSocketSession (Session):
    pass


class WebSession (Session):

    def __init__(self):
        self.queue = []

    def send(self, packet: Packet):
        self.queue.append(packet)


if __name__ == '__main__':
    NeolithServer().start()
