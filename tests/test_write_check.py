"""ops/write_check.py against a fake Home Assistant: refused, ignored, confirmed,
and the refusal to call anything a pass when it could not look."""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ops"))
import write_check  # noqa: E402

ENTITY = write_check.ENTITY


def fake_ha(answer_status: int, answer_body: str, takes: bool):
    machine = {"value": 94.5}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, status, body):
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            assert self.path == "/api/states/" + ENTITY
            self._send(200, json.dumps({"entity_id": ENTITY, "state": str(machine["value"]),
                                        "last_changed": "2026-11-10T14:51:48+00:00"}))

        def do_POST(self):
            assert self.path == "/api/services/number/set_value"
            sent = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if takes and answer_status < 400:
                machine["value"] = sent["value"]
            self._send(answer_status, answer_body)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def ha(monkeypatch):
    servers = []

    def start(status, body, takes):
        server = fake_ha(status, body, takes)
        servers.append(server)
        monkeypatch.setenv("HA_URL", "http://127.0.0.1:%d" % server.server_port)
        monkeypatch.setenv("HA_TOKEN", "not-a-real-token")
        monkeypatch.setattr(write_check, "CONFIRM_S", 1.5)
        return server
    yield start
    for server in servers:
        server.shutdown()


def test_refused(ha, capsys):
    ha(500, '{"message": "Error while setting value 94.6 for number coffee_temp"}', takes=False)
    assert write_check.main(["--set", "94.6"]) == 1
    out = capsys.readouterr().out
    assert "REFUSED" in out and "Error while setting value" in out


def test_ignored(ha, capsys):
    ha(200, "[]", takes=False)
    assert write_check.main(["--set", "94.6"]) == 1
    assert "IGNORED" in capsys.readouterr().out


def test_confirmed(ha, capsys):
    ha(200, "[]", takes=True)
    assert write_check.main(["--set", "94.6"]) == 0
    assert "CONFIRMED: the machine reports 94.6" in capsys.readouterr().out


def test_read_only_by_default(ha, capsys):
    ha(500, "should never be called", takes=False)
    assert write_check.main([]) == 0
    assert "read only" in capsys.readouterr().out


def test_could_not_look_is_not_a_pass(monkeypatch, capsys):
    monkeypatch.delenv("HA_URL", raising=False)
    monkeypatch.delenv("HA_TOKEN", raising=False)
    assert write_check.main(["--set", "94.6"]) == 2
    assert "NOT CHECKED" in capsys.readouterr().out
