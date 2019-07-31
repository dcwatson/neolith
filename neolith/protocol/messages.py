from .base import Action, Notification, Object, String, packet
from .types import EncryptedMessage, Session


@packet('message.send')
class SendMessage (Action):
    recipient = String(doc='The message recipient.', required=True)
    message = String(doc='Unencrypted message text.')
    encrypted = Object(EncryptedMessage, doc='The encrypted (and optionally signed) message.')

    async def handle(self, server, session):
        recipient = server.get(ident=self.recipient)
        await recipient.send(Message(sender=session, message=self.message, encrypted=self.encrypted))


@packet('message')
class Message (Notification):
    sender = Object(Session, doc='The message sender.', required=True)
    message = String(doc='Unencrypted message text.')
    encrypted = Object(EncryptedMessage, doc='The encrypted (and optionally signed) message.')
