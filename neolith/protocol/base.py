import umsgpack

import enum


class Protocol (enum.IntEnum):
    ClientInfo = 1
    ServerInfo = 2
    LoginRequest = 3
    LoginResponse = 4
    UserJoined = 100
    UserLeft = 101
    Chat = 200


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


class PacketType (DataType):
    registered_types = {}

    def __init__(self, kind):
        super().__init__(default=kind, required=True, readonly=True)

    def __set_name__(self, owner, name):
        if name != 'kind':
            raise TypeError('PacketTypes must be named "kind"')
        self.name = name
        PacketType.registered_types[self.default] = owner

    @classmethod
    def instantiate(cls, buf):
        data = umsgpack.unpackb(buf)
        if 'kind' not in data:
            raise ProtocolError('Unable to instantiate packet, missing "kind" field')
        return PacketType.registered_types.get(data['kind'], Packet).unpack(data)


class Int (DataType):
    python_type = int


class String (DataType):
    python_type = str


class Binary (DataType):
    python_type = bytes


class List (DataType):
    python_type = list

    def __init__(self, item_type, **kwargs):
        if not issubclass(item_type, Container):
            raise TypeError('Items in a {} must be Container subclasses'.format(self.__class__.__name__))
        self.item_type = item_type
        super().__init__(**kwargs)

    def check_value(self, instance, value):
        if isinstance(value, self.python_type):
            for item in value:
                if not isinstance(item, self.item_type):
                    raise AttributeError('Values of {}.{} must be of type {}'.format(
                        instance.__class__.__name__, self.name, self.item_type.__name__))
        return super().check_value(instance, value)

    def prepare(self, value):
        return [item.prepare() for item in value if isinstance(item, self.item_type)]

    def unpack(self, value):
        return [self.item_type.unpack(item) for item in value]


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

    def serialize(self) -> bytes:
        return umsgpack.packb(self.prepare())

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
    def deserialize(cls, buf: bytes):
        return cls.unpack(umsgpack.unpackb(buf))


class Packet (Container):
    kind = Int()
    sequence = Int()
    flags = Int()

    response_type = None

    def response(self, **kwargs):
        response_type = self.response_type or Packet
        return response_type(sequence=self.sequence, **kwargs)


# move this stuff...

class User (Container):
    uid = Int()
    nickname = String()
    icon = Binary()

    def __str__(self):
        return '{}:{}'.format(self.uid, self.nickname)


class ClientPacket (Packet):
    pass


class ServerPacket (Packet):
    pass


class LoginResponse (ServerPacket):
    kind = PacketType(Protocol.LoginResponse)
    users = List(User)


class LoginRequest (ClientPacket):
    kind = PacketType(Protocol.LoginRequest)
    username = String()
    password = String()

    response_type = LoginResponse
