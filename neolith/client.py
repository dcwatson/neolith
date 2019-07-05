from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import requests

from neolith.protocol import EncryptedMessage, GetUserList, LoginRequest, Logout, PostChat, Transaction

from .server import SocketSession

import asyncio


class SocketClient:

    async def connected(self, session):
        print('socket connected')
        await session.send(LoginRequest(username='guest', nickname='socketuser'))

    async def disconnected(self, session):
        print('socket disconnected')

    async def handle(self, session, packet):
        print(packet.to_dict())


class WebClient:
    token = None

    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096, backend=default_backend())
        self.public_key = self.private_key.public_key()
        self.pubkey = self.public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ).decode('ascii')
        self.users = {}

    def decrypt(self, message):
        return self.private_key.decrypt(
            message,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        ).decode('utf-8')

    def send(self, packet):
        url = '{}/api/{}'.format(self.endpoint, packet.ident.replace('.', '/'))
        headers = {'X-Neolith-Session': self.token}
        r = requests.post(url, headers=headers, json=packet.prepare())
        for p in Transaction(r.json()):
            p.handle(self)

    def login(self, nickname, username='guest', password=''):
        self.send(LoginRequest(username=username, password=password, nickname=nickname, pubkey=self.pubkey))

    def logout(self):
        self.send(Logout())

    def userlist(self):
        self.send(GetUserList())

    def chat(self, channel, text):
        encrypted = [EncryptedMessage(session_id=ident, data=user.encrypt(text)) for ident, user in self.users.items()]
        self.send(PostChat(channel=channel, encrypted=encrypted))

    def events(self):
        url = '{}/api/events'.format(self.endpoint)
        headers = {'X-Neolith-Session': self.token}
        r = requests.get(url, headers=headers)
        for data in r.json():
            print(data)
            for p in Transaction(data):
                p.handle(self)

    def handle_login_response(self, packet):
        print(packet)
        self.token = packet.token

    def handle_user_list(self, packet):
        print(packet)
        for u in packet.users:
            self.users[u.ident] = u
            print(str(u), '-', u.pubkey)

    def handle_chat_posted(self, packet):
        print(packet.user, packet.channel, self.decrypt(packet.encrypted))


async def main(loop):
    client = SocketClient()
    transport, protocol = await loop.create_connection(
        lambda: SocketSession(client),
        '127.0.0.1', 8120)


if __name__ == '__main__':
    client = WebClient('http://localhost:8080')
    client.login('webuser')
    client.userlist()
    client.chat('public', 'hello world')
    client.events()
    # client.logout()

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(main(loop))

    try:
        loop.run_forever()
    finally:
        client.logout()
