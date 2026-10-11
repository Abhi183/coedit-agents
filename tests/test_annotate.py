from coedit.annotate import annotate_source
from coedit.models import Region, Lease, Edit


def test_annotate_marks_leased_lines_and_recent_edits():
    src = "a = 1\nb = 2\nc = 3\nd = 4\n"
    leases = [Lease(id="x", agent="bob", region=Region("f.py", 2, 3), intent="rename b",
                    created_at=0.0, expires_at=9e9)]
    edits = [Edit(id="e", agent="bob", region=Region("f.py", 4, 4), summary="added d", created_at=1.0)]
    out = annotate_source(src, leases, edits)
    lines = out.splitlines()
    assert lines[0].startswith("   1 |") or lines[0].startswith("1")
    assert "bob" in lines[1] and "rename b" in lines[1]
    assert "bob" in lines[2]
    assert "added d" in lines[3]
    assert "bob" not in lines[0]


def test_annotate_whole_file_lease_shows_header():
    src = "x = 1\n"
    leases = [Lease(id="x", agent="bob", region=Region("f.py"), intent="rewrite",
                    created_at=0.0, expires_at=9e9)]
    out = annotate_source(src, leases, [])
    assert out.splitlines()[0].startswith("# [coedit] whole file leased by bob")
