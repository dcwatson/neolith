from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .base import Binary, Boolean, Container, Int, List, Notification, Object, Packet, Request, Response, String, packet


class Session (Container):
    ident = String()
    username = String()
    hostname = String(default='unknown')
    nickname = String(default='unnamed')
    pubkey = String(doc='Public key in OpenSSH encoding/format.')

    token = None
    authenticated = False

    def send(self, packet: Packet):
        raise NotImplementedError()

    def __str__(self):
        return '{}!{}@{}'.format(self.nickname, self.username, self.hostname)

    def encrypt(self, text):
        public_key = serialization.load_ssh_public_key(self.pubkey.encode('ascii'), default_backend())
        return public_key.encrypt(
            text.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )


class EncryptedMessage (Container):
    session_id = String(required=True)
    data = Binary(required=True)


class Channel (Container):
    name = String()
    topic = String()
    protected = Boolean(default=False)
    private = Boolean(default=False)
    encrypted = Boolean(default=False)

    def __init__(self, name, **kwargs):
        self.name = name
        self.sessions = set()
        self.invitations = set()
        super().__init__(**kwargs)

    def invite(self, session):
        self.invitations.add(session.ident)

    def add(self, session):
        self.sessions.add(session)

    def remove(self, session):
        self.sessions.discard(session)
        self.invitations.discard(session.ident)

    def send(self, packet: Packet):
        for s in self.sessions:
            s.send(packet)
