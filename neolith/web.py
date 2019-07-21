from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates

from neolith import settings
from neolith.models import Account
from neolith.protocol import registered_packets, types

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
        form = await request.form()
        if not await Account.query(username=form['username']).count():
            await Account.insert(
                username=form['username'],
                password=base64.b64decode(form['password']),
                email=form['email'],
                password_salt=base64.b64decode(form['passwordSalt']),
                iterations=int(form['iterations']),
                key_salt=base64.b64decode(form['keySalt']),
                key_iv=base64.b64decode(form['keyIV']),
                public_key=base64.b64decode(form['publicKey']),
                private_key=base64.b64decode(form['privateKey']),
            )
            return RedirectResponse(url='/')
        return RedirectResponse(url='/signup')
    return templates.TemplateResponse('signup.html', {
        'request': request,
        'server_name': settings.SERVER_NAME,
    })
