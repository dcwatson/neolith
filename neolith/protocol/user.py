from .base import List, Notification, Object, Request, Response, packet
from .types import Session


@packet('user.list')
class GetUserList (Request):
    async def handle(self, server, session):
        return UserList(users=list(server.sessions.values()))


@packet('user.listing')
class UserList (Response):
    users = List(Session, doc='A list of all users on the server.')


@packet('user.joined')
class UserJoined (Notification):
    user = Object(Session, doc='The user who joined the server.')


@packet('user.left')
class UserLeft (Notification):
    user = Object(Session, doc='The user who left the server.')


@packet('user.modified')
class UserModified (Notification):
    user = Object(Session, doc='The user who was modified.')
