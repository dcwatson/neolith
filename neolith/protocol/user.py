from .base import Binary, Container, Int, List, Notification, Object, Request, Response, String, packet
from .types import Session


@packet('user.list')
class GetUserList (Request):
    async def handle(self, server, session):
        return UserList(users=list(server.sessions.values()))


@packet('user.listing')
class UserList (Response):
    users = List(Session)


@packet('user.joined')
class UserJoined (Notification):
    user = Object(Session)


@packet('user.left')
class UserLeft (Notification):
    user = Object(Session)  # Maybe just uid/nickname?


@packet('user.modified')
class UserModified (Notification):
    user = Object(Session)
