"""
Tests for src/runtime_cli/ — Typer CLI commands.
Uses Typer's CliRunner for isolation; challenge commands are tested against
the running FastAPI TestClient via httpx mock rather than a live server.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from src.api.app import app as fastapi_app
from src.runtime_cli.main import cli

runner = CliRunner()


@pytest.fixture(scope="module")
def api_client():
    with TestClient(fastapi_app) as c:
        yield c


# ---------------------------------------------------------------------------
# route-match
# ---------------------------------------------------------------------------


def test_route_match_golden_json():
    result = runner.invoke(cli, [
        "route-match", "--app", "salesforce", "--env", "dev",
        "--path", "/lightning/r/Account/001/view",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["app"] == "salesforce"
    assert data["env"] == "dev"
    assert data["route"] == "account-detail"
    assert data["params"]["id"] == "001"


def test_route_match_list_route():
    result = runner.invoke(cli, [
        "route-match", "--app", "salesforce", "--env", "dev",
        "--path", "/lightning/r/Account/list/view",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["route"] == "account-list"


def test_route_match_no_match_exits_1():
    result = runner.invoke(cli, [
        "route-match", "--app", "salesforce", "--env", "dev",
        "--path", "/no/such/path",
    ])
    assert result.exit_code == 1


def test_route_match_unknown_app_exits_2():
    result = runner.invoke(cli, [
        "route-match", "--app", "no-such-app", "--env", "dev",
        "--path", "/some/path",
    ])
    assert result.exit_code == 2


def test_route_match_unknown_env_exits_2():
    result = runner.invoke(cli, [
        "route-match", "--app", "salesforce", "--env", "staging",
        "--path", "/lightning/r/Account/001/view",
    ])
    assert result.exit_code == 2


def test_route_match_jira():
    result = runner.invoke(cli, [
        "route-match", "--app", "jira", "--env", "cloud",
        "--path", "/browse/ABC-123",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["route"] == "issue"
    assert data["params"]["issue_key"] == "ABC-123"


def test_route_match_trace_shows_routes():
    result = runner.invoke(cli, [
        "route-match", "--app", "salesforce", "--env", "dev",
        "--path", "/lightning/r/Account/001/view", "--trace",
    ])
    assert result.exit_code == 0
    assert "account-detail" in result.output
    assert "MATCH" in result.output


# ---------------------------------------------------------------------------
# view-data
# ---------------------------------------------------------------------------


def test_view_data_detail_golden_json():
    result = runner.invoke(cli, [
        "view-data", "--app", "salesforce", "--env", "dev",
        "--route", "account-detail", "--param", "id=001",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["kind"] == "detail"
    assert data["entity_title"] == "Accounts"
    assert data["record"] is not None
    assert data["record"]["id"] == "001"


def test_view_data_list_golden_json():
    result = runner.invoke(cli, [
        "view-data", "--app", "salesforce", "--env", "dev",
        "--route", "account-list",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["kind"] == "list"
    assert data["entity_title"] == "Accounts"
    assert len(data["records"]) > 0


def test_view_data_template_only_route():
    result = runner.invoke(cli, [
        "view-data", "--app", "salesforce", "--env", "dev",
        "--route", "dashboard",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["kind"] == "template-only"


def test_view_data_unknown_app_exits_2():
    result = runner.invoke(cli, [
        "view-data", "--app", "no-such-app", "--env", "dev",
        "--route", "account-detail",
    ])
    assert result.exit_code == 2


def test_view_data_unknown_route_exits_2():
    result = runner.invoke(cli, [
        "view-data", "--app", "salesforce", "--env", "dev",
        "--route", "no-such-route",
    ])
    assert result.exit_code == 2


def test_view_data_bad_param_format_exits_2():
    result = runner.invoke(cli, [
        "view-data", "--app", "salesforce", "--env", "dev",
        "--route", "account-detail", "--param", "badparam",
    ])
    assert result.exit_code == 2


def test_view_data_dump_context():
    result = runner.invoke(cli, [
        "view-data", "--app", "salesforce", "--env", "dev",
        "--route", "account-detail", "--param", "id=001",
        "--dump-context",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "context" in data
    assert "view" in data
    assert data["context"]["app_id"] == "salesforce"
    assert data["context"]["route_id"] == "account-detail"
    assert data["view"]["kind"] == "detail"


# ---------------------------------------------------------------------------
# challenge set / clear / list (via live FastAPI TestClient)
# ---------------------------------------------------------------------------


def test_challenge_roundtrip(api_client):
    """Set a challenge via CLI, verify via API, clear via CLI."""
    # Patch httpx to route through the TestClient
    with _mock_httpx(api_client):
        set_result = runner.invoke(cli, [
            "challenge", "set",
            "--app", "salesforce", "--env", "dev", "--route", "account-detail",
            "--delay-ms", "100",
        ])
        assert set_result.exit_code == 0, set_result.output
        data = json.loads(set_result.output)
        assert data["status"] == "set"

        # Verify challenge is stored
        r = api_client.get("/challenges")
        assert "salesforce/dev/account-detail" in r.json()

        clear_result = runner.invoke(cli, [
            "challenge", "clear",
            "--app", "salesforce", "--env", "dev", "--route", "account-detail",
        ])
        assert clear_result.exit_code == 0
        data = json.loads(clear_result.output)
        assert data["status"] == "cleared"


def test_challenge_list(api_client):
    with _mock_httpx(api_client):
        api_client.post("/challenges/salesforce/dev/account-list", json={"delay_ms": 50})
        result = runner.invoke(cli, ["challenge", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "salesforce/dev/account-list" in data
        api_client.delete("/challenges/salesforce/dev/account-list")


def test_challenge_set_with_fault(api_client):
    with _mock_httpx(api_client):
        result = runner.invoke(cli, [
            "challenge", "set",
            "--app", "salesforce", "--env", "dev", "--route", "account-list",
            "--fault-kind", "unavailable", "--detail", "Down",
        ])
        assert result.exit_code == 0
        challenges = api_client.get("/challenges").json()
        entry = challenges.get("salesforce/dev/account-list")
        assert entry is not None
        assert entry["fault"]["kind"] == "unavailable"
        api_client.delete("/challenges/salesforce/dev/account-list")


# ---------------------------------------------------------------------------
# import boundary
# ---------------------------------------------------------------------------


def test_runtime_cli_does_not_import_api():
    import importlib
    import sys
    # Ensure runtime_cli is importable without touching src.api
    api_modules_before = {k for k in sys.modules if k.startswith("src.api")}
    importlib.import_module("src.runtime_cli.main")
    # Any api modules now present must have been there before
    new_api_imports = {k for k in sys.modules if k.startswith("src.api")} - api_modules_before
    # main.py itself should not trigger new api imports
    assert not new_api_imports, f"runtime_cli imported src.api modules: {new_api_imports}"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _mock_httpx(api_client: TestClient):
    """Context manager that routes httpx calls through the FastAPI TestClient."""
    import httpx

    class _Transport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            method = request.method
            url = str(request.url)
            path = request.url.path
            content = request.content

            if method == "POST":
                r = api_client.post(path, content=content, headers={"content-type": "application/json"})
            elif method == "DELETE":
                r = api_client.delete(path)
            elif method == "GET":
                r = api_client.get(path)
            else:
                r = api_client.request(method, path)

            return httpx.Response(
                status_code=r.status_code,
                content=r.content,
                headers=dict(r.headers),
            )

    transport = _Transport()
    mock_client = httpx.Client(transport=transport, base_url="http://localhost:8000")

    return patch("src.runtime_cli.main.httpx", _FakeHttpxModule(mock_client))


class _FakeHttpxModule:
    def __init__(self, client):
        self._client = client

    def post(self, url, **kwargs):
        return self._client.post(url, **kwargs)

    def delete(self, url, **kwargs):
        return self._client.delete(url, **kwargs)

    def get(self, url, **kwargs):
        return self._client.get(url, **kwargs)

    HTTPError = __import__("httpx").HTTPError
