from .base import List, Notification, Object, Request, Response, packet
from .types import Session


@packet('user.list')
class GetUserList (Request):
    async def handle(self, server, session):
        return UserList(users=list(server.sessions.values()))


@packet('user.listing')
class UserList (Response):
    users = List(Session, doc='A list of all users on the server.', required=True)


@packet('user.joined')
class UserJoined (Notification):
    user = Object(Session, doc='The user who joined the server.', required=True)


@packet('user.left')
class UserLeft (Notification):
    user = Object(Session, doc='The user who left the server.', required=True)


@packet('user.modified')
class UserModified (Notification):
    user = Object(Session, doc='The user who was modified.', required=True)
