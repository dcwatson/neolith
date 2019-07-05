import base64
import re


registered_packets = {}


class ProtocolError (Exception):
    pass


class DataType:
    python_type = None

    def __init__(self, doc="", default=None, required=False, readonly=False):
        self.doc = doc
        self.default = default
        self.required = required
        self.readonly = readonly

    def __get__(self, instance, owner):
        if not instance:
            return self
        if self.name not in instance.__dict__:
            value = self.default() if callable(self.default) else self.default
            if self.readonly:
                return value
            # Set the default value the first time it's accessed, so it's not changing on every access.
            self.__set__(instance, value)
        return instance.__dict__[self.name]

    def __set__(self, instance, value):
        if self.readonly:
            raise AttributeError('{}.{} is immutable'.format(instance.__class__.__name__, self.name))
        instance.__dict__[self.name] = self.check_value(instance, value)

    def __set_name__(self, owner, name):
        self.name = name

    def check_value(self, instance, value):
        if value is None or isinstance(value, self.python_type):
            return value
        raise AttributeError('{}.{} must be of type {} (got {})'.format(
            instance.__class__.__name__, self.name, self.python_type.__name__, value.__class__.__name__))

    def prepare(self, value):
        return value

    def unpack(self, value):
        return value

    def describe(self):
        default = self.default
        if callable(default):
            default = '{}()'.format(self.default.__name__)
        return {
            self.name: {
                'type': self.python_type.__name__,
                'doc': self.doc,
                'default': default,
                'required': self.required,
                'readonly': self.readonly,
            }
        }


class Int (DataType):
    python_type = int


class String (DataType):
    python_type = str


class Boolean (DataType):
    python_type = bool


class Binary (DataType):
    python_type = bytes

    def prepare(self, value):
        return base64.b64encode(value).decode('ascii') if value is not None else None

    def unpack(self, value):
        return base64.b64decode(value) if value is not None else None


class Object (DataType):

    def __init__(self, item_type, **kwargs):
        # TODO: add a way to exclude fields from the Container
        if not issubclass(item_type, Container):
            raise TypeError('Objects may only be Container subclasses'.format(self.__class__.__name__))
        self.python_type = item_type
        super().__init__(**kwargs)

    def prepare(self, value):
        return value.prepare() if value is not None else None

    def unpack(self, value):
        return self.python_type.unpack(value)


class List (DataType):
    python_type = list

    def __init__(self, item_type, **kwargs):
        self.item_type = item_type
        if 'default' not in kwargs:
            kwargs['default'] = list
        super().__init__(**kwargs)

    def check_value(self, instance, value):
        if isinstance(value, self.python_type):
            for item in value:
                if not isinstance(item, self.item_type):
                    raise AttributeError('Values of {}.{} must be of type {}'.format(
                        instance.__class__.__name__, self.name, self.item_type.__name__))
        return super().check_value(instance, value)

    def prepare(self, value):
        prepared = []
        if value is None:
            return prepared
        for item in value:
            if isinstance(item, self.item_type):
                prepared.append(item.prepare() if isinstance(item, Container) else item)
        return prepared

    def unpack(self, value):
        if value is None:
            return []
        if issubclass(self.item_type, Container):
            return [self.item_type.unpack(item) for item in value]
        else:
            return [self.item_type(item) for item in value]

    def describe(self):
        description = super().describe()
        description[self.name]['item_type'] = self.item_type.__name__
        return description


class Container:

    def __init__(self, **kwargs):
        for field, value in kwargs.items():
            setattr(self, field, value)

    def prepare(self):
        data = {}
        for klass in self.__class__.mro():
            for name, field in vars(klass).items():
                if isinstance(field, DataType) and name not in data:
                    value = getattr(self, name)
                    if value is None and field.required:
                        raise ProtocolError('{}.{} is required to have a value'.format(self.__class__.__name__, name))
                    data[name] = field.prepare(value)
        return data

    @classmethod
    def unpack(cls, data: dict):
        instance = cls()
        seen = set()
        for klass in cls.mro():
            for name, field in vars(klass).items():
                if isinstance(field, DataType):
                    if name not in seen and not field.readonly:
                        setattr(instance, name, field.unpack(data.get(name)))
                    seen.add(name)
        return instance

    @classmethod
    def describe(cls):
        description = {}
        for klass in cls.mro():
            for name, field in vars(klass).items():
                if isinstance(field, DataType):
                    description.update(field.describe())
        return description


class Sendable:

    def to_dict(self):
        raise NotImplementedError()


class Packet (Container, Sendable):
    ident = None

    def to_dict(self) -> dict:
        return {self.ident: self.prepare()}

    @classmethod
    def find(cls, ident: str):
        global registered_packets
        return registered_packets.get(ident)


class Transaction (Sendable):
    txid = None

    def __init__(self, data=None, txid=None):
        self.txid = txid
        self.packets = []
        if isinstance(data, dict):
            for ident, payload in data.items():
                if ident == 'txid':
                    self.txid = payload
                elif ident in registered_packets:
                    if isinstance(payload, dict):
                        payload = [payload]
                    for fields in payload:
                        self.packets.append(registered_packets[ident].unpack(fields))

    def __iter__(self):
        for p in self.packets:
            yield p

    @property
    def empty(self):
        return self.txid is None and not self.packets

    def response(self):
        return self.__class__(txid=self.txid)

    def add(self, packet):
        if packet:
            self.packets.append(packet)

    def to_dict(self):
        data = {}
        if self.txid:
            data['txid'] = self.txid
        for p in self.packets:
            data.setdefault(p.ident, []).append(p.prepare())
        return data


def packet(ident, requires_auth=True):
    global registered_packets

    def _decorator(packet_class):
        assert issubclass(packet_class, Packet)
        if ident in registered_packets:
            # TODO: make this a log info/warning to allow customizing packets
            raise TypeError('Packet {} is already registered as {}'.format(ident, registered_packets[ident].__name__))
        packet_class.ident = ident
        if issubclass(packet_class, ClientPacket):
            packet_class.requires_auth = requires_auth
        registered_packets[ident] = packet_class
        return packet_class
    return _decorator


def snake(name):
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class ClientPacket (Packet):
    requires_auth = True

    async def handle(self, server, session):
        pass


class ServerPacket (Packet):

    def handle(self, client):
        methods = (
            'handle_{}'.format(self.__class__.__name__),
            'handle_{}'.format(snake(self.__class__.__name__)),
        )
        for name in methods:
            handler = getattr(client, name, None)
            if handler and callable(handler):
                return handler(self)


class Request (ClientPacket):
    """ A packet initiated by the client that expects a response. """
    pass


class Action (ClientPacket):
    """ A packet sent by the client that does not expect a response. """
    pass


class Response (ServerPacket):
    """ A packet sent by the server in response to a request. """
    pass


class Notification (ServerPacket):
    """ A packet sent by the server not in response to a request. """
    pass
