from starlette.config import Config


config = Config(".env")


DEBUG = config('DEBUG', cast=bool, default=False)
DATABASE = config('DATABASE', default='neolith.db')

SOCKET_BIND = config('SOCKET_BIND', default='0.0.0.0')
SOCKET_PORT = config('SOCKET_PORT', cast=int, default=8120)

WEB_BIND = config('WEB_BIND', default='0.0.0.0')
WEB_PORT = config('WEB_PORT', cast=int, default=8080)

SERVER_NAME = config('SERVER_NAME', default='Neolith')
PUBLIC_CHANNEL = config('PUBLIC_CHANNEL', default='public')
AUTO_JOIN = config('AUTO_JOIN', cast=bool, default=False)

ENABLE_WEB_CLIENT = config('ENABLE_WEB_CLIENT', cast=bool, default=True)
ENABLE_DOCS = config('ENABLE_DOCS', cast=bool, default=True)
ENABLE_SIGNUP = config('ENABLE_SIGNUP', cast=bool, default=True)
