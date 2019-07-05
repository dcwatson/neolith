from .base import Action, Request, Response, String, packet


@packet('login', requires_auth=False)
class LoginRequest (Request):
    username = String(doc='The username to log in with.', default='guest')
    password = String(doc='The password for the associated username.')
    nickname = String(required=True, doc='Nicknames must be unique on the server.')
    pubkey = String(doc='Public key in OpenSSH encoding/format.')

    async def handle(self, server, session):
        session.username = self.username
        session.nickname = self.nickname
        session.pubkey = self.pubkey
        server.authenticate(session)
        return LoginResponse(session_id=session.ident, token=session.token)


@packet('login.response')
class LoginResponse (Response):
    session_id = String(doc='Public session ID used to identify users on the server.')
    token = String(doc='Private authentication token for your session, for use with the web APIs.')


@packet('logout', requires_auth=False)
class Logout (Action):
    async def handle(self, server, session):
        await server.disconnected(session)
