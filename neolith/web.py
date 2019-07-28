from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates

from neolith import settings
from neolith.models import Account
from neolith.protocol import KeyPair, PasswordSpec, registered_packets, types

import base64
import os


template_dir = os.path.join(os.path.dirname(__file__), 'templates')
templates = Jinja2Templates(directory=template_dir)


async def docs(request):
    data_types = []
    for name in dir(types):
        try:
            t = getattr(types, name)
            if t.__module__ == 'neolith.protocol.types':
                data_types.append(t)
        except AttributeError:
            pass
    return templates.TemplateResponse('docs/protocol.html', {
        'request': request,
        'registered_packets': registered_packets,
        'data_types': data_types,
    })


async def client(request):
    return templates.TemplateResponse('client.html', {
        'request': request,
        'server_name': settings.SERVER_NAME,
    })


async def signup(request):
    if request.method == 'POST':
        data = await request.json()
        if await Account.query(username=data['username']).count():
            return JSONResponse({'error': 'This username is already taken.'}, status_code=400)
        if await Account.query(email=data['email']).count():
            return JSONResponse({'error': 'This email address is already used by another account.'}, status_code=400)
        await Account.insert(
            username=data['username'],
            email=data['email'],
            password_spec=PasswordSpec.unpack(data['password_spec']),
            stored_key=base64.b64decode(data['stored_key']),
            server_key=base64.b64decode(data['server_key']),
            x25519=KeyPair.unpack(data['x25519']),
            ed25519=KeyPair.unpack(data['ed25519']),
            active=True,
            verified=False
        )
        return JSONResponse({'redirect': '/'})
    return templates.TemplateResponse('signup.html', {
        'request': request,
        'server_name': settings.SERVER_NAME,
    })
