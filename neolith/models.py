import dorm

from .protocol.types import KeyPair, PasswordSpec

import base64


Binary = dorm.Column("text", to_sql=base64.b64encode, to_python=base64.b64decode)
KeyPairColumn = dorm.Column("text", to_sql=KeyPair.to_sql, to_python=KeyPair.to_python)


class Account (dorm.AsyncTable):
    columns = {
        'username': dorm.String(unique=True, to_sql=dorm.lower),
        'email': dorm.Email(unique=True),
        'password_spec': dorm.Column("text", to_sql=PasswordSpec.to_sql, to_python=PasswordSpec.to_python),
        'password': Binary,
        'ecdh': KeyPairColumn,
        'ecdsa': KeyPairColumn,
        'active': dorm.Boolean(default=0),
        'verified': dorm.Boolean(default=0),
    }
