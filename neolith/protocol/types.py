from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .base import Binary, Boolean, Container, Sendable, String


class Session (Container):
    ident = String(doc='Public session ID used to identify users on the server.')
    username = String(doc='The username of the session.')
    hostname = String(doc='The hostname for the session, may be fake.', default='unknown')
    nickname = String(doc='The nickname for the session, must be unique across all sessions.', default='unnamed')
    public_key = Binary(doc='Public key; DER-encoded SPKI.')

    token = None
    authenticated = False
    account = None

    def __str__(self):
        return '{}!{}@{}'.format(self.nickname, self.username, self.hostname)

    async def send(self, data: Sendable):
        raise NotImplementedError()

    def encrypt(self, text):
        public_key = serialization.load_der_public_key(self.pubkey, default_backend())
        return public_key.encrypt(
            text.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )


class EncryptedMessage (Container):
    session_id = String(doc='The session ID this message is encrypted for.', required=True)
    data = Binary(doc='The encrypted message.', required=True)


class Channel (Container):
    name = String(doc='The unique name of this channel.')
    topic = String(doc='Topic of the channel')
    protected = Boolean(doc='Whether this channel can be removed or not.', default=False)
    private = Boolean(doc='Whether this channel is invitation-only or not.', default=False)
    encrypted = Boolean(doc='Whether posts to this channel must be encrypted or not.', default=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sessions = set()
        self.invitations = set()

    def invite(self, session):
        self.invitations.add(session.ident)

    def add(self, session):
        if session in self.sessions:
            return False
        self.sessions.add(session)
        return True

    def remove(self, session):
        self.sessions.discard(session)
        self.invitations.discard(session.ident)

    async def send(self, data: Sendable):
        for s in self.sessions:
            if s.authenticated:
                await s.send(data)
