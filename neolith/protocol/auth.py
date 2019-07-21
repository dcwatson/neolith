from ..models import Account
from .base import Action, Binary, Integer, ProtocolError, Request, Response, String, packet


@packet('challenge', requires_auth=False)
class LoginChallenge (Request):
    username = String(doc='The username you are about to log in with.')

    async def handle(self, server, session):
        account = await Account.query(username=self.username).get()
        # TODO: send deterministic challenge for unknown users.
        if account is None:
            raise ProtocolError('Unknown user.')
        session.username = self.username
        session.account = account
        return ChallengeResponse(
            session_id=session.ident,
            iterations=account.iterations,
            password_salt=account.password_salt
        )


@packet('challenge.response')
class ChallengeResponse (Response):
    session_id = String(doc='Public session ID used to identify users on the server.')
    iterations = Integer(doc='Number of iterations to use when hashing the password (PBKDF2).')
    password_salt = Binary(doc='The salt to use when hashing the password (PBKDF2) for login.')


@packet('login', requires_auth=False)
class LoginRequest (Request):
    session_id = String(doc='Public session ID used to identify users on the server.')
    password = Binary(doc='The hashed password (PBKDF2) for the associated username.')
    nickname = String(required=True, doc='Nicknames must be unique on the server.')

    async def handle(self, server, session):
        session.nickname = self.nickname
        if session.account is None or session.account.password != self.password:
            raise ProtocolError('Login failed.')
        session.public_key = session.account.public_key
        await server.authenticate(session)
        return LoginResponse(
            session_id=session.ident,
            token=session.token,
            server_name=server.name,
            private_key=session.account.private_key,
            iterations=session.account.iterations,
            key_salt=session.account.key_salt,
            key_iv=session.account.key_iv
        )


@packet('login.response')
class LoginResponse (Response):
    session_id = String(doc='Public session ID used to identify users on the server.')
    token = String(doc='Private authentication token for your session, for use with the web API.')
    server_name = String(doc='Name of the server.')
    private_key = Binary(doc='The encrypted private key for the account.')
    iterations = Integer(doc='Number of iterations to use when hashing the password (PBKDF2).')
    key_salt = Binary(doc='The salt used when hashing the password to generate the AES-GCM key for the private key.')
    key_iv = Binary(doc='The IV used to generate the AES-GCM key for the private key.')


@packet('logout', requires_auth=False)
class Logout (Action):
    async def handle(self, server, session):
        await server.disconnected(session)
