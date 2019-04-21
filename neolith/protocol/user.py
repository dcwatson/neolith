from .base import Binary, Container, Int, List, Notification, Object, PacketType, Request, Response, String


class User (Container):
    uid = Int()
    nickname = String()
    icon = Binary()

    def __str__(self):
        return '{}:{}'.format(self.uid, self.nickname)


class LoginRequest (Request):
    kind = PacketType(3)
    username = String()
    password = String()


class LoginResponse (Response):
    kind = PacketType(4)
    uid = Int()


class GetUserList (Request):
    kind = PacketType(100)


class UserList (Response):
    kind = PacketType(101)
    users = List(User)


class UserJoined (Notification):
    kind = PacketType(102)
    user = Object(User)


class UserLeft (Notification):
    kind = PacketType(103)
    user = Object(User)  # Maybe just uid/nickname?


class UserChanged (Notification):
    kind = PacketType(104)
    user = Object(User)
