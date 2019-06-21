from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
# from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

import os


template_dir = os.path.join(os.path.dirname(__file__), 'templates')
templates = Jinja2Templates(directory=template_dir)

app = Starlette()
app.debug = True


@app.route('/')
async def index(request):
    from neolith.protocol import registered_packets, Session, Channel, EncryptedMessage
    data_types = [Session, Channel, EncryptedMessage]  # TODO: make this dynamic
    return templates.TemplateResponse('docs/protocol.html', {
        'request': request,
        'registered_packets': registered_packets,
        'data_types': data_types,
    })
