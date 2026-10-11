import pytest
from mcp.client import Client
from coedit.server import build_server


@pytest.mark.anyio
async def test_two_agents_over_mcp(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n\ndef g():\n    return f()\n")
    alice = build_server(tmp_path, "alice")
    bob = build_server(tmp_path, "bob")
    async with Client(alice) as a, Client(bob) as b:
        tools = {t.name for t in (await a.list_tools()).tools}
        assert {"coedit_claim", "coedit_status", "coedit_read", "coedit_record",
                "coedit_send", "coedit_release", "coedit_renew", "coedit_whoami"} <= tools
        r = await a.call_tool("coedit_claim", {"path": "m.py", "intent": "speed up f", "symbol": "f"})
        assert '"ok": true' in r.content[0].text
        r = await b.call_tool("coedit_claim", {"path": "m.py", "intent": "edit f", "symbol": "f"})
        assert '"ok": false' in r.content[0].text and "alice" in r.content[0].text
        r = await b.call_tool("coedit_read", {"path": "m.py"})
        assert "alice: speed up f" in r.content[0].text
        r = await b.call_tool("coedit_claim", {"path": "m.py", "intent": "change g", "symbol": "g"})
        assert '"severity": "semantic"' in r.content[0].text
