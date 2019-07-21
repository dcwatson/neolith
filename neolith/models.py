import dorm


class Account (dorm.AsyncTable):
    columns = {
        'username': dorm.String(unique=True, to_sql=dorm.lower),
        'password': dorm.Binary,
        'password_salt': dorm.Binary,
        'iterations': dorm.Integer,
        'email': dorm.Email(unique=True),
        'public_key': dorm.Binary,
        'private_key': dorm.Binary,
        'key_salt': dorm.Binary,
        'key_iv': dorm.Binary,
        'active': dorm.Boolean(default=0),
        'verified': dorm.Boolean(default=0),
    }
