from starlette.applications import Starlette
from starlette.templating import Jinja2Templates

from neolith.protocol import registered_packets, types

import os


template_dir = os.path.join(os.path.dirname(__file__), 'templates')
templates = Jinja2Templates(directory=template_dir)

app = Starlette()
app.debug = True


@app.route('/')
async def index(request):
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
