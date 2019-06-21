from .base import Action, Binary, Boolean, Container, Int, List, Notification, Object, Request, Response, String, packet
from .types import Channel, EncryptedMessage, Session


# Client actions/requests

@packet('channel.post')
class PostChat (Action):
    channel = String(required=True)
    chat = String()
    encrypted = List(EncryptedMessage)
    emote = Boolean(default=False)

    async def handle(self, server, session):
        channel = server.channels[self.channel]
        if channel.encrypted:
            messages = {e.session_id: e.data for e in self.encrypted}
            for s in channel.sessions:
                if s.pubkey and s.ident in messages:
                    await s.send(ChatPosted(channel=self.channel,
                           encrypted=messages[s.ident], emote=self.emote, user=session))
        else:
            await channel.send(ChatPosted(channel=self.channel, chat=self.chat, emote=self.emote, user=session))


@packet('channel.list')
class GetChannels (Request):
    async def handle(self, server, session):
        channels = list(server.channels.channels.values())
        return ChannelList(channels=channels)


@packet('channel.users')
class GetChannelUsers (Request):
    channel = String()

    async def handle(self, server, session):
        channel = server.channels[self.channel]
        return ChannelUsers(channel=self.channel, users=list(channel.sessions))


@packet('channel.create')
class CreateChannel (Request):
    channel = String()


@packet('channel.invite')
class InviteUsers (Request):
    channel = String()
    uids = List(int)


@packet('channel.decline')
class DeclineInvitation (Request):
    channel = String()


@packet('channel.join')
class JoinChannel (Request):
    channel = String()


@packet('channel.leave')
class LeaveChannel (Request):
    channel = String()


@packet('channel.modify')
class ModifyChannel (Request):
    channel = String()
    topic = String()


# Server responses/notifications


@packet('channel.posted')
class ChatPosted (Notification):
    channel = String()
    chat = String()
    encrypted = Binary()
    emote = Boolean()
    user = Object(Session)


@packet('channel.listing')
class ChannelList (Response):
    channels = List(Channel)


@packet('channel.userlist')
class ChannelUsers (Response):
    channel = String()
    users = List(Session)


@packet('channel.invited')
class ChannelInvitation (Notification):
    channel = Object(Channel)
    user = Object(Session)


@packet('channel.joined')
class ChannelJoin (Notification):
    channel = String()


@packet('channel.left')
class ChannelLeave (Notification):
    channel = String()


@packet('channel.modified')
class ChannelModified (Notification):
    channel = String()
