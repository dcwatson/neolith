import pytest

from neolith.protocol.base import Binary, Int, Packet, PacketType, ProtocolError, String


class SomeResponse (Packet):
    reply = String()


class SomeRequest (Packet):
    kind = PacketType(13)
    sequence = Int(required=True)
    nickname = String()
    icon = Binary()

    response_type = SomeResponse


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
