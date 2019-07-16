from starlette.templating import Jinja2Templates

from neolith import settings
from neolith.protocol import registered_packets, types

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
