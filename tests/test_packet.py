import pytest

from neolith.protocol.base import Binary, Container, Int, List, Packet, PacketType, ProtocolError, String


class SomeType (Container):
    name = String()
    flags = Int()


class SomeResponse (Packet):
    reply = String()
    objects = List(SomeType)


class SomeRequest (Packet):
    kind = PacketType(13)
    sequence = Int(required=True)
    nickname = String()
    icon = Binary()
    ints = List(int)


def test_round_trip():
    p1 = SomeRequest(sequence=1, nickname="unnamed")
    p2 = SomeRequest.deserialize(p1.serialize())
    assert p1.kind == p2.kind
    assert p1.sequence == p2.sequence
    assert p1.nickname == p2.nickname
    assert p1.icon == p2.icon


def test_readonly():
    p1 = SomeRequest()
    with pytest.raises(AttributeError):
        p1.kind = 22


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
