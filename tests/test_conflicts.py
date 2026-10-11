import textwrap
from coedit.conflicts import classify, Severity, semantic_conflicts
from coedit.models import Region, Lease

SRC = textwrap.dedent('''
    def parse_config(path):
        return open(path).read()

    def load(path):
        return parse_config(path)

    def unrelated():
        return 1
''')


def lease(agent, start, end, intent="work"):
    return Lease(id=agent, agent=agent, region=Region("a.py", start, end),
                 intent=intent, created_at=0.0, expires_at=9e9)


def test_disjoint():
    r = classify(Region("a.py", 1, 3), [lease("bob", 8, 9)])
    assert r.severity is Severity.NONE


def test_adjacent_is_a_warning():
    r = classify(Region("a.py", 1, 3), [lease("bob", 5, 6)])
    assert r.severity is Severity.ADJACENT
    assert "bob" in r.detail


def test_same_region_blocks():
    r = classify(Region("a.py", 1, 3), [lease("bob", 2, 6)])
    assert r.severity is Severity.OVERLAP


def test_semantic_conflict_when_editing_symbol_other_agent_depends_on():
    # bob holds `load` (lines 5-6), which calls parse_config. alice edits parse_config.
    conflicts = semantic_conflicts(SRC, Region("a.py", 2, 3), [lease("bob", 5, 6)])
    assert conflicts and conflicts[0].symbol == "parse_config" and conflicts[0].agent == "bob"


def test_no_semantic_conflict_for_unrelated_symbol():
    conflicts = semantic_conflicts(SRC, Region("a.py", 8, 9), [lease("bob", 5, 6)])
    assert conflicts == []


def test_classify_includes_semantic_when_source_given():
    r = classify(Region("a.py", 2, 3), [lease("bob", 5, 6)], source=SRC)
    assert r.severity is Severity.SEMANTIC
