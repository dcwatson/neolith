from .base import Action, Boolean, Container, Int, List, Notification, Object, PacketType, Request, Response, String
from .user import User


class Channel (Container):
    name = String()
    topic = String()
    flags = Int()
    num_users = Int()


# Client actions/requests

class PostChat (Action):
    kind = PacketType(201)
    channel = String()
    chat = String()
    emote = Boolean()


class GetChannels (Request):
    kind = PacketType(202)


class CreateChannel (Request):
    kind = PacketType(203)
    channel = String()
    flags = Int()


class InviteUsers (Request):
    kind = PacketType(204)
    uids = List(int)


class DeclineInvitation (Request):
    kind = PacketType(205)
    channel = String()


class JoinChannel (Request):
    kind = PacketType(206)
    channel = String()


class LeaveChannel (Request):
    kind = PacketType(207)
    channel = String()


class ModifyChannel (Request):
    kind = PacketType(208)
    channel = String()
    topic = String()
    flags = Int()


# Server responses/notifications


class ChatPosted (Notification):
    kind = PacketType(200)
    channel = String()
    chat = String()
    emote = Boolean()
    user = Object(User)


class ChannelList (Response):
    kind = PacketType(220)
    channels = List(Channel)


class Invitation (Notification):
    kind = PacketType(221)
    channel = String()


class ChannelJoin (Notification):
    kind = PacketType(222)
    channel = String()


class ChannelLeave (Notification):
    kind = PacketType(223)
    channel = String()


class ChannelModified (Notification):
    kind = PacketType(224)
    channel = String()
