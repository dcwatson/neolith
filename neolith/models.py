import dorm
import base64


Binary = dorm.Column("text", to_sql=base64.b64encode, to_python=base64.b64decode)

class Account (dorm.AsyncTable):
    columns = {
        'username': dorm.String(unique=True, to_sql=dorm.lower),
        'password': Binary,
        'password_salt': Binary,
        'iterations': dorm.Integer,
        'email': dorm.Email(unique=True),
        'public_key': Binary,
        'private_key': Binary,
        'key_salt': Binary,
        'key_iv': Binary,
        'active': dorm.Boolean(default=0),
        'verified': dorm.Boolean(default=0),
    }
