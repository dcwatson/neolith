from .base import Action, Binary, Object, ProtocolError, Request, Response, String, packet
from .types import KeyPair, PasswordSpec

import hashlib
import hmac
import os


def xor(b1, b2):
    return bytes([a ^ b for a, b in zip(b1, b2)])


@packet('challenge', requires_auth=False)
class LoginChallenge (Request):
    username = String(doc='The username you are about to log in with.', required=True)
    nonce = Binary(doc='Random client nonce.', required=True)

    async def handle(self, server, session):
        # Account imports neolith.protocol.types
        from ..models import Account
        account = await Account.query(username=self.username).get()
        # TODO: send deterministic challenge for unknown users.
        if account is None:
            raise ProtocolError('Unknown user.')
        session.username = self.username
        session.account = account
        nonce = self.nonce + os.urandom(16)
        return ChallengeResponse(
            server_name=server.name,
            token=session.token,  # Only send for web sessions?
            password_spec=account.password_spec,
            nonce=nonce
        )


@packet('challenge.response')
class ChallengeResponse (Response):
    server_name = String(doc='Name of the server.', required=True)
    token = String(doc='Private authentication token for your session, for use with the web API.')
    password_spec = Object(
        PasswordSpec, doc='Information about how the password should be hashed on the client.', required=True)
    nonce = Binary(doc='Combined client+server nonce', required=True)


@packet('login', requires_auth=False)
class LoginRequest (Request):
    nonce = Binary(doc='Combined client+server nonce', required=True)
    proof = Binary(doc='SCRAM client proof.', required=True)
    nickname = String(doc='Nicknames must be unique on the server.', required=True)

    async def handle(self, server, session):
        if session.account is None:
            raise ProtocolError('Login failed.')
        server_signature = hmac.new(session.account.server_key, self.nonce, 'sha256').digest()
        client_signature = hmac.new(session.account.stored_key, self.nonce, 'sha256').digest()
        client_key = xor(client_signature, self.proof)
        stored_key = hashlib.sha256(client_key).digest()
        if session.account.stored_key != stored_key:
            raise ProtocolError('Login failed.')
        session.nickname = self.nickname
        if session.account.x25519:
            session.x25519 = session.account.x25519.public_key
        if session.account.ed25519:
            session.ed25519 = session.account.ed25519.public_key
        await server.authenticate(session)
        return LoginResponse(
            proof=server_signature,
            session_id=session.ident,
            server_key=server.secret_key,
            x25519=session.account.x25519,
            ed25519=session.account.ed25519
        )


@packet('login.response')
class LoginResponse (Response):
    proof = Binary(doc='SCRAM server proof.', required=True)
    session_id = String(doc='Your public session ID (used to identify users on the server).', required=True)
    server_key = Binary(doc='Random key for this server, used to salt channel keys.', required=True)
    x25519 = Object(KeyPair, doc='The x25519 keys for the account.')
    ed25519 = Object(KeyPair, doc='The ed25519 keys for the account.')


@packet('logout', requires_auth=False)
class Logout (Action):
    async def handle(self, server, session):
        await server.disconnected(session)
