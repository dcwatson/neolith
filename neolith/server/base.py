from neolith.protocol import NeolithDelegate, NeolithProtocol, ServerInfo


class NeolithServer (NeolithDelegate):

    def __init__(self, loop):
        self.loop = loop

    def start(self, address='0.0.0.0', port=8120):
        self.loop.run_until_complete(
            self.loop.create_server(lambda: NeolithProtocol(self), address, port)
        )

    def notify_connect(self, protocol):
        print('client connected')
        protocol.write(ServerInfo(name='neolith-server'))

    def notify_packet(self, protocol, packet):
        print(protocol, packet)
