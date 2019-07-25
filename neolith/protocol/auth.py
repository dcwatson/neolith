from .base import Action, Binary, Object, ProtocolError, Request, Response, String, packet
from .types import KeyPair, PasswordSpec


@packet('challenge', requires_auth=False)
class LoginChallenge (Request):
    username = String(doc='The username you are about to log in with.')

    async def handle(self, server, session):
        # Account imports neolith.protocol.types
        from ..models import Account
        account = await Account.query(username=self.username).get()
        # TODO: send deterministic challenge for unknown users.
        if account is None:
            raise ProtocolError('Unknown user.')
        session.username = self.username
        session.account = account
        return ChallengeResponse(
            server_name=server.name,
            token=session.token,
            password_spec=account.password_spec
        )


@packet('challenge.response')
class ChallengeResponse (Response):
    server_name = String(doc='Name of the server.')
    token = String(doc='Private authentication token for your session, for use with the web API.')
    password_spec = Object(PasswordSpec, doc='Information about how the password should be hashed on the client.')


@packet('login', requires_auth=False)
class LoginRequest (Request):
    password = Binary(doc='The hashed password (PBKDF2) for the associated username.')
    nickname = String(required=True, doc='Nicknames must be unique on the server.')

    async def handle(self, server, session):
        if session.account is None or session.account.password != self.password:
            raise ProtocolError('Login failed.')
        session.nickname = self.nickname
        session.x25519 = session.account.x25519.public_key
        session.ed25519 = session.account.ed25519.public_key
        await server.authenticate(session)
        return LoginResponse(
            session_id=session.ident,
            server_key=server.secret_key,
            x25519=session.account.x25519,
            ed25519=session.account.ed25519
        )


@packet('login.response')
class LoginResponse (Response):
    session_id = String(doc='Public session ID used to identify users on the server.')
    server_key = Binary(doc='Random key for this server, used to salt channel keys.')
    x25519 = Object(KeyPair, doc='The x25519 keys for the account.')
    ed25519 = Object(KeyPair, doc='The ed25519 keys for the account.')


@packet('logout', requires_auth=False)
class Logout (Action):
    async def handle(self, server, session):
        await server.disconnected(session)
