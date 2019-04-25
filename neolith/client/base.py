from neolith.protocol import ClientInfo, NeolithDelegate, NeolithProtocol, ServerPacket

import asyncio


class NeolithClient (NeolithDelegate):

    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.protocol = None

    def connect(self, address='127.0.0.1', port=8120):
        self.loop.run_until_complete(
            self.loop.create_connection(lambda: NeolithProtocol(self), address, port)
        )

    def notify_connect(self, protocol):
        self.protocol = protocol
        protocol.write(ClientInfo(name='neolith-client'))

    def notify_packet(self, protocol, packet):
        assert isinstance(packet, ServerPacket)
        packet.handle(self)
