import pytest

from neolith.protocol import Binary, Container, Int, List, Packet, ProtocolError, String, packet


class SomeType (Container):
    name = String()
    flags = Int()


@packet('some.response')
class SomeResponse (Packet):
    reply = String()
    objects = List(SomeType)


@packet('some.request')
class SomeRequest (Packet):
    sequence = Int(required=True)
    nickname = String()
    icon = Binary()
    ints = List(int)
    version = Int(readonly=True, default=1)


def test_round_trip():
    p1 = SomeRequest(sequence=1, nickname="unnamed", icon=b'123')
    for p2 in Packet.deserialize(p1.serialize()):
        assert p2.__class__ is SomeRequest
        assert p1.ident == p2.ident
        assert p1.sequence == p2.sequence
        assert p1.nickname == p2.nickname
        assert p1.icon == p2.icon


def test_readonly():
    p1 = SomeRequest()
    with pytest.raises(AttributeError):
        p1.version = 22


def test_types():
    p1 = SomeRequest()
    with pytest.raises(AttributeError):
        p1.nickname = 13
    with pytest.raises(AttributeError):
        p1.sequence = "nope"
    with pytest.raises(AttributeError):
        p1.icon = "nope"


def test_required():
    p1 = SomeRequest()
    p1.sequence = None
    with pytest.raises(ProtocolError):
        p1.serialize()


def test_lists():
    p1 = SomeRequest(sequence=2, ints=[1, 2, 3, 5, 8])
    for p2 in Packet.deserialize(p1.serialize()):
        assert p1.ints == p2.ints
    p3 = SomeResponse(
        reply="hello there",
        objects=[
            SomeType(name="foo", flags=1),
            SomeType(name="bar", flags=2),
        ]
    )
    for p4 in Packet.deserialize(p3.serialize()):
        assert ["foo", "bar"] == [t.name for t in p4.objects]
