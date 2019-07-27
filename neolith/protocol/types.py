from .base import Binary, Boolean, Container, Integer, Object, Sendable, String

import hashlib


class PasswordSpec (Container):
    algorithm = String(doc='Algorithm used to generate the password hash.', default='pbkdf2_sha256', required=True)
    salt = Binary(doc='Salt used when generating the password hash.', required=True)
    iterations = Integer(
        doc='Number of iterations used in the password hashing function (if applicable).', default=200000)

    def generate(self, password):
        assert self.algorithm == 'pbkdf2_sha256'
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), self.salt, self.iterations)


class KeyPair (Container):
    key_spec = Object(PasswordSpec, doc='How to derive the AES-GCM decryption key from a password.', required=True)
    nonce = Binary(doc='Nonce used for the AES-GCM encryption of the key data.', required=True)
    data = Binary(doc='The AES-GCM encrypted private key data.', required=True)
    public_key = Binary(doc='The public key.')


class Session (Container):
    ident = String(doc='Public session ID used to identify users on the server.', required=True)
    username = String(doc='The username of the session.', required=True)
    hostname = String(doc='The hostname for the session, may be fake.', default='unknown', required=True)
    nickname = String(doc='The nickname for the session, must be unique across all sessions.', required=True)
    x25519 = Binary(doc='Public x25519 key.')
    ed25519 = Binary(doc='Public ed25519 key.')

    token = None
    authenticated = False
    account = None

    def __str__(self):
        return '{}!{}@{}'.format(self.nickname, self.username, self.hostname)

    async def send(self, data: Sendable):
        raise NotImplementedError()


class EncryptedMessage (Container):
    nonce = Binary(doc='Nonce used for the AES-GCM encryption of the message data.', required=True)
    data = Binary(doc='The AES-GCM encrypted message.', required=True)
    signature = Binary(doc='Signature of the message data (before encryption).')


class Channel (Container):
    name = String(doc='The unique name of this channel.', required=True)
    topic = String(doc='Topic of the channel')
    protected = Boolean(doc='Whether this channel can be removed or not.', default=False)
    private = Boolean(doc='Whether this channel is invitation-only or not.', default=False)
    encrypted = Boolean(doc='Whether posts to this channel must be encrypted or not.', default=False)

    # Store this to check on join, but no need to give it to clients.
    key_hash = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sessions = set()
        self.invitations = set()

    @property
    def irc_name(self):
        return '#{}'.format(self.name)

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
