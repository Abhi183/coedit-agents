import json
from coedit.cli import main


def test_init_creates_state_and_mcp_config(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "init"]) == 0
    assert (tmp_path / ".coedit" / "state.db").exists()
    cfg = json.loads((tmp_path / ".mcp.json").read_text())
    assert cfg["mcpServers"]["coedit"]["args"] == ["serve"]


def test_init_merges_existing_mcp_config(tmp_path):
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    main(["--root", str(tmp_path), "init"])
    cfg = json.loads((tmp_path / ".mcp.json").read_text())
    assert set(cfg["mcpServers"]) == {"other", "coedit"}


def test_status_without_init_fails(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "status"]) == 1


def test_status_prints_leases(tmp_path, capsys):
    main(["--root", str(tmp_path), "init"])
    from coedit.service import Coordinator
    (tmp_path / "f.py").write_text("x = 1\n")
    Coordinator(tmp_path, "alice").claim("f.py", intent="tweak x", start_line=1, end_line=1)
    capsys.readouterr()
    assert main(["--root", str(tmp_path), "status"]) == 0
    out = capsys.readouterr().out
    assert "alice" in out and "tweak x" in out
