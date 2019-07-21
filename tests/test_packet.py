import pytest

from neolith.protocol import Binary, Container, Integer, List, Packet, ProtocolError, String, Transaction, packet


class SomeType (Container):
    name = String()
    flags = Integer()


@packet('some.response')
class SomeResponse (Packet):
    reply = String()
    objects = List(SomeType)


@packet('some.request')
class SomeRequest (Packet):
    sequence = Integer(required=True)
    nickname = String()
    icon = Binary()
    ints = List(int)
    version = Integer(readonly=True, default=1)


def test_round_trip():
    p1 = SomeRequest(sequence=1, nickname="unnamed", icon=b'123')
    for p2 in Transaction(p1.to_dict()).packets:
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
        p1.to_dict()


def test_lists():
    p1 = SomeRequest(sequence=2, ints=[1, 2, 3, 5, 8])
    for p2 in Transaction(p1.to_dict()).packets:
        assert p1.ints == p2.ints
    p3 = SomeResponse(
        reply="hello there",
        objects=[
            SomeType(name="foo", flags=1),
            SomeType(name="bar", flags=2),
        ]
    )
    for p4 in Transaction(p3.to_dict()).packets:
        assert ["foo", "bar"] == [t.name for t in p4.objects]
