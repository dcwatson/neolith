from neolith.protocol import ClientInfo, NeolithDelegate, NeolithProtocol


class NeolithClient (NeolithDelegate):

    def __init__(self, loop):
        self.loop = loop

    def connect(self, address='127.0.0.1', port=8120):
        self.loop.run_until_complete(
            self.loop.create_connection(lambda: NeolithProtocol(self), address, port)
        )

    def notify_connect(self, protocol):
        print('connected')
        protocol.write(ClientInfo(name='neolith-client'))

    def notify_packet(self, protocol, packet):
        print(protocol, packet)
