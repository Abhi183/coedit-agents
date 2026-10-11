import pytest
from coedit.store import Store, LeaseConflict
from coedit.models import Region


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "state.db")


def test_claim_and_list(store):
    lease = store.claim("alice", Region(path="a.py", start_line=1, end_line=10),
                        intent="add parser", ttl=60, now=1000.0)
    active = store.active_leases(now=1001.0)
    assert [l.id for l in active] == [lease.id]
    assert active[0].intent == "add parser"


def test_claim_overlapping_region_by_other_agent_raises(store):
    store.claim("alice", Region(path="a.py", start_line=1, end_line=10), "x", ttl=60, now=0.0)
    with pytest.raises(LeaseConflict) as exc:
        store.claim("bob", Region(path="a.py", start_line=5, end_line=8), "y", ttl=60, now=1.0)
    assert exc.value.holders[0].agent == "alice"


def test_same_agent_can_reclaim_own_region(store):
    store.claim("alice", Region(path="a.py", start_line=1, end_line=10), "x", ttl=60, now=0.0)
    store.claim("alice", Region(path="a.py", start_line=5, end_line=8), "x2", ttl=60, now=1.0)
    assert len(store.active_leases(now=2.0)) == 2


def test_expired_lease_does_not_block(store):
    store.claim("alice", Region(path="a.py"), "x", ttl=10, now=0.0)
    store.claim("bob", Region(path="a.py"), "y", ttl=10, now=11.0)
    active = store.active_leases(now=12.0)
    assert [l.agent for l in active] == ["bob"]


def test_release_and_heartbeat(store):
    lease = store.claim("alice", Region(path="a.py"), "x", ttl=10, now=0.0)
    store.heartbeat(lease.id, ttl=10, now=9.0)
    assert store.active_leases(now=15.0)
    store.release(lease.id)
    assert store.active_leases(now=15.0) == []


def test_edits_and_messages_persist(store):
    store.record_edit("alice", Region(path="a.py", start_line=1, end_line=2), "fix", now=5.0)
    assert store.edits_since(0.0)[0].summary == "fix"
    store.send_message("alice", "bob", "need parse_config", now=6.0)
    inbox = store.inbox("bob", since=0.0)
    assert inbox[0].body == "need parse_config"
    assert store.inbox("alice", since=0.0) == []


def test_two_store_handles_share_state(tmp_path):
    a = Store(tmp_path / "s.db")
    b = Store(tmp_path / "s.db")
    a.claim("alice", Region(path="z.py"), "x", ttl=60, now=0.0)
    assert b.active_leases(now=1.0)[0].agent == "alice"
