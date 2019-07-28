import dorm

from .protocol.types import KeyPair, PasswordSpec

import base64
import hashlib
import hmac


def safe_b64encode(b):
    return None if b is None else base64.b64encode(b)


def safe_b64decode(s):
    return None if s is None else base64.b64decode(s)


Binary = dorm.Column("text", to_sql=safe_b64encode, to_python=safe_b64decode)
KeyPairColumn = dorm.Column("text", to_sql=KeyPair.to_sql, to_python=KeyPair.to_python)


class Account (dorm.AsyncTable):
    columns = {
        'username': dorm.String(unique=True, to_sql=dorm.lower),
        'email': dorm.Email(unique=True),
        'password_spec': dorm.Column("text", to_sql=PasswordSpec.to_sql, to_python=PasswordSpec.to_python),
        'stored_key': Binary,
        'server_key': Binary,
        'x25519': KeyPairColumn,
        'ed25519': KeyPairColumn,
        'active': dorm.Boolean(default=0),
        'verified': dorm.Boolean(default=0),
    }

    def check_password(self, password):
        salted_password = self.password_spec.generate(password)
        client_key = hmac.new(salted_password, b'Client Key', 'sha256').digest()
        stored_key = hashlib.sha256(client_key).digest()
        return stored_key == self.stored_key
