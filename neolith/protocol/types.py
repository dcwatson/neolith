from .base import Binary, Boolean, Container, Integer, Object, Sendable, String


class PasswordSpec (Container):
    algorithm = String(doc='Algorithm used to generate the password hash.', default='pbkdf2_sha256')
    salt = Binary(doc='Salt used when generating the password hash.')
    iterations = Integer(
        doc='Number of iterations used in the password hashing function (if applicable).', default=200000)


class KeyPair (Container):
    key_spec = Object(PasswordSpec, doc='How to derive the AES-GCM decryption key from a password.')
    nonce = Binary(doc='Nonce used for the AES-GCM encryption of the key data.')
    data = Binary(doc='The AES-GCM encrypted private key data.')
    public_key = Binary(doc='The public key.')


class Session (Container):
    ident = String(doc='Public session ID used to identify users on the server.')
    username = String(doc='The username of the session.')
    hostname = String(doc='The hostname for the session, may be fake.', default='unknown')
    nickname = String(doc='The nickname for the session, must be unique across all sessions.', default='unnamed')
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
    nonce = Binary(doc='Nonce used for the AES-GCM encryption of the message data.')
    data = Binary(doc='The AES-GCM encrypted message.', required=True)
    signature = Binary(doc='Signature of the message data (before encryption).')


class Channel (Container):
    name = String(doc='The unique name of this channel.')
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
