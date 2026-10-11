from coedit.models import Region, Lease, Edit, Message


def test_region_overlap_same_file_lines():
    a = Region(path="a.py", start_line=1, end_line=10)
    b = Region(path="a.py", start_line=10, end_line=20)
    c = Region(path="a.py", start_line=11, end_line=20)
    d = Region(path="b.py", start_line=1, end_line=5)
    assert a.overlaps(b)
    assert not a.overlaps(c)
    assert not a.overlaps(d)


def test_region_adjacency():
    a = Region(path="a.py", start_line=1, end_line=10)
    c = Region(path="a.py", start_line=11, end_line=20)
    far = Region(path="a.py", start_line=30, end_line=40)
    assert a.is_adjacent(c, gap=2)
    assert not a.is_adjacent(far, gap=2)


def test_whole_file_region_overlaps_everything_in_file():
    whole = Region(path="a.py")
    part = Region(path="a.py", start_line=50, end_line=60)
    assert whole.overlaps(part)
    assert part.overlaps(whole)


def test_lease_is_frozen_and_expiry():
    lease = Lease(id="l1", agent="alice", region=Region(path="a.py"),
                  intent="refactor", created_at=100.0, expires_at=200.0)
    assert lease.is_expired(now=201.0)
    assert not lease.is_expired(now=150.0)
    try:
        lease.agent = "bob"  # type: ignore[misc]
        raise AssertionError("lease should be immutable")
    except AttributeError:
        pass


def test_models_round_trip_dict():
    e = Edit(id="e1", agent="alice", region=Region(path="a.py", start_line=3, end_line=4),
             summary="fix bug", created_at=1.0)
    assert Edit.from_dict(e.to_dict()) == e
    m = Message(id="m1", sender="alice", recipient="bob", body="hi", created_at=1.0)
    assert Message.from_dict(m.to_dict()) == m
