from .base import Action, Binary, Int, Request, Response, String, packet


@packet('login', requires_auth=False)
class LoginRequest (Request):
    username = String(default='guest')
    password = String()
    nickname = String(required=True)
    pubkey = String(doc='Public key in OpenSSH encoding/format.')

    async def handle(self, server, session):
        session.username = self.username
        session.nickname = self.nickname
        session.pubkey = self.pubkey
        server.authenticate(session)
        return LoginResponse(session_id=session.ident, token=session.token)


@packet('login.response')
class LoginResponse (Response):
    session_id = String()
    token = String()


@packet('logout', requires_auth=False)
class Logout (Action):
    async def handle(self, server, session):
        server.disconnected(session)
