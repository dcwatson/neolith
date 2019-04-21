import umsgpack


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
        if self.default in PacketType.registered_types:
            other = PacketType.registered_types[self.default]
            raise TypeError('PacketType({}) is already registered to {}'.format(self.default, other.__name__))
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


class Boolean (DataType):
    python_type = bool


class Binary (DataType):
    python_type = bytes


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
        if issubclass(self.item_type, Container):
            return [item.prepare() for item in value if isinstance(item, self.item_type)]
        else:
            return [item for item in value if isinstance(item, self.item_type)]

    def unpack(self, value):
        if issubclass(self.item_type, Container):
            return [self.item_type.unpack(item) for item in value]
        else:
            return value


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

    def response(self, cls=None, **kwargs):
        response_class = cls or Response
        return response_class(sequence=self.sequence, **kwargs)


class Request (Packet):
    """ A packet initiated by the client that expects a response. """
    pass


class Response (Packet):
    """ A packet sent by the server in response to a request. """
    pass


class Action (Packet):
    """ A packet sent by the client that does not expect a response. """
    pass


class Notification (Packet):
    """ A packet sent by the server not in response to a request. """
    pass


class ClientInfo (Request):
    kind = PacketType(1)
    name = String()
    protocol = Int(default=1)


class ServerInfo (Packet):
    kind = PacketType(2)
    name = String()
    protocol = Int(default=1)
