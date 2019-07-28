import dorm

from neolith.models import Account
from neolith.protocol import PasswordSpec, Sendable, Session, Transaction
from neolith.server import NeolithServer

import asyncio
import base64
import hashlib
import hmac
import os
import unittest


dorm.setup(models=[Account])


b64 = base64.b64encode


def xor(b1, b2):
    return bytes([a ^ b for a, b in zip(b1, b2)])


def async_test(coro):
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


class DummySession (Session):

    def __init__(self):
        self.outbox = []

    async def send(self, data: Sendable):
        self.outbox.append(data)

    def last(self, ident):
        # Finds the last received packet of the given type.
        for tx in reversed(self.outbox):
            packet = tx.first(ident)
            if packet:
                return packet
        return None


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.server = NeolithServer()

    async def create_account(self, username='test', password='secret'):
        spec = PasswordSpec(salt=os.urandom(32))
        salted_password = spec.generate(password)
        client_key = hmac.new(salted_password, b'Client Key', 'sha256').digest()
        server_key = hmac.new(salted_password, b'Server Key', 'sha256').digest()
        stored_key = hashlib.sha256(client_key).digest()
        return await Account.insert(
            username='testuser',
            email='test@example.com',
            password_spec=spec,
            stored_key=stored_key,
            server_key=server_key,
            active=True,
            verified=True
        )

    @async_test
    async def test_scram_login(self):
        account = await self.create_account()
        session = DummySession()
        await self.server.connected(session)
        nonce = os.urandom(16)
        await self.server.handle(session, Transaction({
            'challenge': {
                'username': account.username,
                'nonce': b64(nonce),
            }
        }))
        response = session.last('challenge.response')
        self.assertTrue(response.nonce.startswith(nonce))
        salted_password = account.password_spec.generate('secret')
        client_key = hmac.new(salted_password, b'Client Key', 'sha256').digest()
        server_key = hmac.new(salted_password, b'Server Key', 'sha256').digest()
        stored_key = hashlib.sha256(client_key).digest()
        # We use the combined client+server nonce as the SCRAM AuthMessage.
        client_signature = hmac.new(stored_key, response.nonce, 'sha256').digest()
        server_signature = hmac.new(server_key, response.nonce, 'sha256').digest()
        client_proof = xor(client_key, client_signature)
        await self.server.handle(session, Transaction({
            'login': {
                'nonce': b64(response.nonce),
                'proof': b64(client_proof),
                'nickname': 'neolith'
            }
        }))
        success = session.last('login.response')
        self.assertEqual(server_signature, success.proof)
        await self.server.disconnected(session)
