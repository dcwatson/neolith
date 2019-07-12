from starlette.config import Config
from starlette.datastructures import URL, Secret

import binascii
import os


config = Config(".env")


DEBUG = config('DEBUG', cast=bool, default=False)
SECRET_KEY = config('SECRET_KEY', cast=Secret, default=binascii.hexlify(os.urandom(16)))
DATABASE_URL = config('DATABASE_URL', cast=URL, default='sqlite://:memory:')

SOCKET_BIND = config('SOCKET_BIND', default='0.0.0.0')
SOCKET_PORT = config('SOCKET_PORT', cast=int, default=8120)

WEB_BIND = config('WEB_BIND', default='0.0.0.0')
WEB_PORT = config('WEB_PORT', cast=int, default=8080)

SERVER_NAME = config('SERVER_NAME', default='Neolith')
PUBLIC_CHANNEL = config('PUBLIC_CHANNEL', default='public')
