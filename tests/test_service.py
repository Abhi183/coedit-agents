import textwrap
import pytest
from coedit.service import Coordinator

SRC = textwrap.dedent('''
    def parse_config(path):
        return open(path).read()

    def load(path):
        return parse_config(path)
''').lstrip()


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "app.py").write_text(SRC)
    return tmp_path


def test_claim_by_symbol_resolves_lines(repo):
    alice = Coordinator(repo, "alice")
    result = alice.claim("app.py", intent="harden parser", symbol="parse_config", ttl=60)
    assert result["ok"] and result["lease"]["region"]["start_line"] == 1
    assert result["lease"]["region"]["end_line"] == 2


def test_overlapping_claim_is_refused_with_holder_info(repo):
    alice, bob = Coordinator(repo, "alice"), Coordinator(repo, "bob")
    alice.claim("app.py", intent="harden parser", symbol="parse_config", ttl=60)
    result = bob.claim("app.py", intent="rewrite", start_line=1, end_line=5, ttl=60)
    assert not result["ok"] and result["severity"] == "overlap"
    assert result["holders"][0]["agent"] == "alice"


def test_semantic_claim_is_allowed_but_warned(repo):
    alice, bob = Coordinator(repo, "alice"), Coordinator(repo, "bob")
    alice.claim("app.py", intent="harden parser", symbol="parse_config", ttl=60)
    result = bob.claim("app.py", intent="change loader", symbol="load", ttl=60)
    assert result["ok"] and result["severity"] == "semantic"
    assert "parse_config" in result["warning"]


def test_read_annotated_shows_other_agent(repo):
    alice, bob = Coordinator(repo, "alice"), Coordinator(repo, "bob")
    alice.claim("app.py", intent="harden parser", symbol="parse_config", ttl=60)
    text = bob.read("app.py")
    assert "alice: harden parser" in text.splitlines()[0]


def test_status_and_messages(repo):
    alice, bob = Coordinator(repo, "alice"), Coordinator(repo, "bob")
    alice.claim("app.py", intent="harden parser", symbol="parse_config", ttl=60)
    alice.record_edit("app.py", "added validation", symbol="parse_config")
    alice.send("bob", "parse_config now raises on missing file")
    status = bob.status()
    assert status["leases"][0]["agent"] == "alice"
    assert status["recent_edits"][0]["summary"] == "added validation"
    assert status["inbox"][0]["body"].startswith("parse_config")
    assert bob.status()["inbox"] == [], "messages are delivered once"


def test_release_all(repo):
    alice = Coordinator(repo, "alice")
    alice.claim("app.py", intent="x", symbol="load", ttl=60)
    assert alice.release()["released"] == 1
    assert alice.status()["leases"] == []


def test_claim_unknown_symbol_errors(repo):
    alice = Coordinator(repo, "alice")
    result = alice.claim("app.py", intent="x", symbol="nope", ttl=60)
    assert not result["ok"] and "not found" in result["error"]


def test_read_refuses_paths_outside_repo(repo):
    alice = Coordinator(repo, "alice")
    assert "outside repository" in alice.read("/etc/hosts")
    assert "outside repository" in alice.read("../../etc/hosts")


def test_paths_are_normalized_so_leases_cannot_be_bypassed(repo):
    alice, bob = Coordinator(repo, "alice"), Coordinator(repo, "bob")
    alice.claim("app.py", intent="x", start_line=1, end_line=2)
    result = bob.claim("./app.py", intent="y", start_line=1, end_line=2)
    assert not result["ok"]
    result = bob.claim(str(repo / "app.py"), intent="y", start_line=1, end_line=2)
    assert not result["ok"]


def test_only_holder_can_release_or_renew(repo):
    alice, bob = Coordinator(repo, "alice"), Coordinator(repo, "bob")
    lease_id = alice.claim("app.py", intent="x", symbol="load")["lease"]["id"]
    assert not bob.release(lease_id)["ok"]
    assert not bob.renew(lease_id)["ok"]
    assert alice.renew(lease_id)["ok"]
    assert alice.release(lease_id)["ok"]
    assert not alice.renew(lease_id)["ok"], "renewing a released lease fails"


def test_partial_line_range_is_an_error(repo):
    alice = Coordinator(repo, "alice")
    result = alice.claim("app.py", intent="x", start_line=5)
    assert not result["ok"] and "both" in result["error"]


def test_ttl_is_validated(repo):
    alice = Coordinator(repo, "alice")
    assert not alice.claim("app.py", intent="x", ttl=0)["ok"]
    assert not alice.claim("app.py", intent="x", ttl=10**9)["ok"]
