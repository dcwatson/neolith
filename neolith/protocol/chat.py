from .base import (
    Action, Boolean, Dictionary, List, Notification, Object, ProtocolError, Request, Response, String, packet)
from .types import Channel, EncryptedMessage, Session


# Client actions/requests

@packet('channel.post')
class PostChat (Action):
    channel = String(doc='The channel name to post to.', required=True)
    chat = String(doc='The chat to post, if the channel is not encrypted.')
    encrypted = Dictionary(EncryptedMessage,
        doc='The encrypted (and optionally signed) messagees, if the channel is encrypted.')
    emote = Boolean(default=False, doc='Whether the chat is an emote (action) or not.')

    async def handle(self, server, session):
        channel = server.channels[self.channel]
        if session not in channel.sessions:
            raise ProtocolError('You are not in this channel.')
        if channel.encrypted:
            if set(self.encrypted) != set([s.ident for s in channel.authenticated_sessions]):
                raise ProtocolError('You must encrypt chat for all members of the channel.')
            for s in channel.authenticated_sessions:
                await s.send(ChatPosted(
                    channel=self.channel,
                    encrypted=self.encrypted[s.ident],
                    emote=self.emote,
                    user=session
                ))
        else:
            await channel.send(ChatPosted(
                channel=self.channel,
                chat=self.chat,
                emote=self.emote,
                user=session
            ))


@packet('channel.list')
class GetChannels (Request):
    async def handle(self, server, session):
        channels = list(server.channels.channels.values())
        return ChannelList(channels=channels)


@packet('channel.users')
class GetChannelUsers (Request):
    channel = String(doc='The channel name to get a list of users for.', required=True)

    async def handle(self, server, session):
        channel = server.channels[self.channel]
        if session not in channel.sessions:
            raise ProtocolError('You are not in this channel.')
        return ChannelUsers(channel=self.channel, users=list(channel.sessions))


@packet('channel.create')
class CreateChannel (Request):
    channel = Object(Channel, doc='The channel to create.', required=True)

    async def handle(self, server, session):
        if self.channel.name in server.channels:
            raise ProtocolError('A channel named "{}" already exists.'.format(self.channel.name))
        server.channels.add(self.channel)
        # TODO: auto-join?
        await server.broadcast(ChannelCreated(channel=self.channel))


@packet('channel.invite')
class InviteUser (Request):
    session_id = String(doc='The user to invite.', required=True)
    channel = String(doc='The channel name to invite the specified user to.', required=True)
    channel_key = Object(EncryptedMessage, doc='The channel key, encrypted by the sender for the invited user.')
    message = String(doc='A message to accompany the invitation.')


@packet('channel.decline')
class DeclineInvitation (Request):
    channel = String(doc='The channel name you are declining the invitation for.', required=True)


@packet('channel.join')
class JoinChannel (Request):
    channel = String(doc='The channel name you wish to join.', required=True)

    async def handle(self, server, session):
        channel = server.channels[self.channel]
        if session not in channel.sessions:
            await channel.send(ChannelJoin(channel=self.channel, user=session))
            channel.add(session)
        return ChannelUsers(channel=self.channel, users=list(channel.sessions))


@packet('channel.leave')
class LeaveChannel (Request):
    channel = String(doc='The channel name you wish to leave.', required=True)

    async def handle(self, server, session):
        channel = server.channels[self.channel]
        if session in channel.sessions:
            channel.remove(session)
            await channel.send(ChannelLeave(channel=self.channel, user=session))


@packet('channel.modify')
class ModifyChannel (Request):
    channel = String(doc='The channel name to modify.', required=True)
    topic = String(doc='The topic to set for the channel.')


# Server responses/notifications


@packet('channel.posted')
class ChatPosted (Notification):
    channel = String(doc='The channel name this chat was posted to.', required=True)
    chat = String(doc='The posted chat, if the channel is not encrypted.')
    encrypted = Object(EncryptedMessage,
        doc='The encrypted (and optionally signed) message, if the channel is encrypted.')
    emote = Boolean(default=False, doc='Whether the posted chat is an emote (action) or not.')
    user = Object(Session, doc='The user who posted the chat.', required=True)


@packet('channel.listing')
class ChannelList (Response):
    channels = List(Channel, doc='A list of all channels visible to you.', required=True)


@packet('channel.userlist')
class ChannelUsers (Response):
    channel = String(doc='The channel name that the associated users are for.', required=True)
    users = List(Session, doc='A list of users in the channel.')


@packet('channel.created')
class ChannelCreated (Response):
    channel = Object(Channel, doc='The channel that was created.', required=True)


@packet('channel.invited')
class ChannelInvitation (Notification):
    channel = Object(Channel, doc='The channel you are being invited to.', required=True)
    user = Object(Session, doc='The user inviting you to the channel.', required=True)
    channel_key = Object(EncryptedMessage, doc='The channel key, encrypted by the sender for the invited user.')
    message = String(doc='The invitation message.')


@packet('channel.joined')
class ChannelJoin (Notification):
    channel = String(doc='The channel name that the user joined.', required=True)
    user = Object(Session, doc='The user who joined the channel.', required=True)


@packet('channel.left')
class ChannelLeave (Notification):
    channel = String(doc='The channel name that the user left.', required=True)
    user = Object(Session, doc='The user who left the channel.', required=True)


@packet('channel.modified')
class ChannelModified (Notification):
    channel = Object(Channel, doc='The channel that was modified.', required=True)
