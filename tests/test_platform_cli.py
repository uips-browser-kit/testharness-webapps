"""
Tests for src/platform_cli/main.py — all commands.
Uses typer.testing.CliRunner; httpx and subprocess are mocked throughout.
"""
import importlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.platform_cli.main import cli

runner = CliRunner()

_FIXTURES = Path(__file__).parent / "fixtures" / "configs"
_VALID_MINIMAL = str(_FIXTURES / "valid" / "minimal.yaml")
_DUP_HOST = str(_FIXTURES / "validate-errors" / "duplicate_host.yaml")
_MISSING_ID = str(_FIXTURES / "invalid" / "missing_app_id.yaml")
_DUP_ROUTE = str(_FIXTURES / "validate-errors" / "duplicate_route_id.yaml")


# ---------------------------------------------------------------------------
# import boundary
# ---------------------------------------------------------------------------


def test_platform_cli_does_not_import_backend_api_frontend():
    forbidden = {"src.backend", "src.api", "src.frontend"}
    before = {k for k in sys.modules if any(k == f or k.startswith(f + ".") for f in forbidden)}
    importlib.import_module("src.platform_cli.main")
    after = {k for k in sys.modules if any(k == f or k.startswith(f + ".") for f in forbidden)}
    assert not (after - before), f"platform_cli imported forbidden modules: {after - before}"


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_valid_config():
    r = runner.invoke(cli, ["validate", "--config", _VALID_MINIMAL])
    assert r.exit_code == 0
    assert "OK" in r.stdout


def test_validate_duplicate_host():
    r = runner.invoke(cli, ["validate", "--config", _DUP_HOST])
    assert r.exit_code == 1
    assert "duplicate-host" in r.output


def test_validate_missing_app_id():
    r = runner.invoke(cli, ["validate", "--config", _MISSING_ID])
    assert r.exit_code == 1


def test_validate_duplicate_route_id():
    r = runner.invoke(cli, ["validate", "--config", _DUP_ROUTE])
    assert r.exit_code == 1
    assert "duplicate-route-id" in r.output


def test_validate_config_not_found():
    r = runner.invoke(cli, ["validate", "--config", "no-such.yaml"])
    assert r.exit_code == 2


def test_validate_check_templates_missing_file(tmp_path):
    cfg = tmp_path / "h.yaml"
    cfg.write_text(
        "apps:\n"
        "  - id: tpl-app\n"
        "    vendor: T\n"
        "    product: P\n"
        "    environments:\n"
        "      dev:\n"
        "        host: tpl-dev.local\n"
        "    routes:\n"
        "      - id: home\n"
        "        path: /\n"
        "        pattern_type: path\n"
        "        template: home\n"
    )
    r = runner.invoke(cli, ["validate", "--config", str(cfg), "--check-templates"])
    assert r.exit_code == 1
    assert "missing-template" in r.output


def test_validate_check_data_files_missing_file(tmp_path):
    cfg = tmp_path / "h.yaml"
    cfg.write_text(
        "apps:\n"
        "  - id: data-app\n"
        "    vendor: T\n"
        "    product: P\n"
        "    environments:\n"
        "      dev:\n"
        "        host: data-dev.local\n"
        "    routes:\n"
        "      - id: list\n"
        "        path: /items\n"
        "        pattern_type: path\n"
        "        data_entity: items\n"
    )
    r = runner.invoke(cli, ["validate", "--config", str(cfg), "--check-data-files"])
    assert r.exit_code == 1
    assert "missing-data-file" in r.output


def test_validate_cli_config_check_templates(tmp_path):
    cfg = tmp_path / "h.yaml"
    cfg.write_text(
        "cli:\n"
        "  validate:\n"
        "    check_templates: true\n"
        "apps:\n"
        "  - id: ct-app\n"
        "    vendor: T\n"
        "    product: P\n"
        "    environments:\n"
        "      dev:\n"
        "        host: ct-dev.local\n"
        "    routes:\n"
        "      - id: home\n"
        "        path: /\n"
        "        pattern_type: path\n"
        "        template: home\n"
    )
    r = runner.invoke(cli, ["validate", "--config", str(cfg)])
    assert r.exit_code == 1
    assert "missing-template" in r.output


# ---------------------------------------------------------------------------
# generate-caddy
# ---------------------------------------------------------------------------


def test_generate_caddy_creates_file(tmp_path):
    out = tmp_path / "Caddyfile"
    r = runner.invoke(cli, ["generate-caddy", "--config", _VALID_MINIMAL, "--out", str(out)])
    assert r.exit_code == 0
    assert out.exists()


def test_generate_caddy_contains_env_host(tmp_path):
    out = tmp_path / "Caddyfile"
    runner.invoke(cli, ["generate-caddy", "--config", _VALID_MINIMAL, "--out", str(out)])
    content = out.read_text()
    assert "minimal-app-dev.local" in content


def test_generate_caddy_harness_env_headers(tmp_path):
    out = tmp_path / "Caddyfile"
    runner.invoke(cli, ["generate-caddy", "--config", _VALID_MINIMAL, "--out", str(out)])
    content = out.read_text()
    assert "X-Harness-App" in content
    assert "X-Harness-Env" in content


def test_generate_caddy_static_blocks_present(tmp_path):
    out = tmp_path / "Caddyfile"
    runner.invoke(cli, ["generate-caddy", "--config", _VALID_MINIMAL, "--out", str(out)])
    content = out.read_text()
    assert "harness.local" in content
    assert "idp.local" in content
    assert "metrics.local" in content


def test_generate_caddy_injects_x_request_id_conditionally(tmp_path):
    out = tmp_path / "Caddyfile"
    runner.invoke(cli, ["generate-caddy", "--config", _VALID_MINIMAL, "--out", str(out)])
    content = out.read_text()
    assert "@no_reqid not header X-Request-ID *" in content
    assert "request_header @no_reqid X-Request-ID {uuid}" in content


def test_generate_caddy_harness_host_override(tmp_path):
    out = tmp_path / "Caddyfile"
    runner.invoke(cli, [
        "generate-caddy", "--config", _VALID_MINIMAL, "--out", str(out),
        "--harness-host", "custom-harness.local",
    ])
    content = out.read_text()
    assert "custom-harness.local" in content


def test_generate_caddy_idp_host_override(tmp_path):
    out = tmp_path / "Caddyfile"
    runner.invoke(cli, [
        "generate-caddy", "--config", _VALID_MINIMAL, "--out", str(out),
        "--idp-host", "custom-idp.local",
    ])
    content = out.read_text()
    assert "custom-idp.local" in content


def test_generate_caddy_config_not_found(tmp_path):
    out = tmp_path / "Caddyfile"
    r = runner.invoke(cli, ["generate-caddy", "--config", "no-such.yaml", "--out", str(out)])
    assert r.exit_code == 2


def test_generate_caddy_unwritable_out(tmp_path):
    unwritable = tmp_path / "no-dir" / "nested" / "Caddyfile"
    with patch("src.platform_cli.main._atomic_write", side_effect=OSError("permission denied")):
        r = runner.invoke(cli, ["generate-caddy", "--config", _VALID_MINIMAL, "--out", str(unwritable)])
    assert r.exit_code == 4


def test_generate_caddy_harness_host_from_cli_config(tmp_path):
    cfg = tmp_path / "h.yaml"
    cfg.write_text(
        "cli:\n"
        "  caddy:\n"
        "    harness_host: my-harness.local\n"
        "apps:\n"
        "  - id: a\n"
        "    vendor: V\n"
        "    product: P\n"
        "    environments:\n"
        "      dev:\n"
        "        host: a-dev.local\n"
        "    routes:\n"
        "      - id: home\n"
        "        path: /\n"
        "        pattern_type: path\n"
    )
    out = tmp_path / "Caddyfile"
    runner.invoke(cli, ["generate-caddy", "--config", str(cfg), "--out", str(out)])
    assert "my-harness.local" in out.read_text()


# ---------------------------------------------------------------------------
# generate-prometheus
# ---------------------------------------------------------------------------


def test_generate_prometheus_creates_file(tmp_path):
    out = tmp_path / "prometheus.yml"
    r = runner.invoke(cli, ["generate-prometheus", "--config", _VALID_MINIMAL, "--out", str(out)])
    assert r.exit_code == 0
    assert out.exists()


def test_generate_prometheus_job_name(tmp_path):
    out = tmp_path / "prometheus.yml"
    runner.invoke(cli, ["generate-prometheus", "--config", _VALID_MINIMAL, "--out", str(out)])
    assert "job_name: harness" in out.read_text()


def test_generate_prometheus_default_target(tmp_path):
    out = tmp_path / "prometheus.yml"
    runner.invoke(cli, ["generate-prometheus", "--config", _VALID_MINIMAL, "--out", str(out)])
    assert "harness:8000" in out.read_text()


def test_generate_prometheus_scrape_interval_from_yaml(tmp_path):
    cfg = tmp_path / "h.yaml"
    cfg.write_text(
        "prometheus:\n"
        "  scrape_interval: 30s\n"
        "apps:\n"
        "  - id: a\n"
        "    vendor: V\n"
        "    product: P\n"
        "    environments:\n"
        "      dev:\n"
        "        host: a-dev.local\n"
        "    routes:\n"
        "      - id: home\n"
        "        path: /\n"
        "        pattern_type: path\n"
    )
    out = tmp_path / "prometheus.yml"
    runner.invoke(cli, ["generate-prometheus", "--config", str(cfg), "--out", str(out)])
    assert "scrape_interval: 30s" in out.read_text()


def test_generate_prometheus_missing_section_defaults_15s(tmp_path):
    out = tmp_path / "prometheus.yml"
    runner.invoke(cli, ["generate-prometheus", "--config", _VALID_MINIMAL, "--out", str(out)])
    assert "scrape_interval: 15s" in out.read_text()


def test_generate_prometheus_target_override(tmp_path):
    out = tmp_path / "prometheus.yml"
    runner.invoke(cli, [
        "generate-prometheus", "--config", _VALID_MINIMAL, "--out", str(out),
        "--target", "custom-host:9000",
    ])
    assert "custom-host:9000" in out.read_text()


def test_generate_prometheus_unwritable_out():
    with patch("src.platform_cli.main._atomic_write", side_effect=OSError("permission denied")):
        r = runner.invoke(cli, ["generate-prometheus", "--config", _VALID_MINIMAL, "--out", "/fake/prometheus.yml"])
    assert r.exit_code == 4


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------


def test_seed_default_invocation():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        r = runner.invoke(cli, ["seed", "--config", _VALID_MINIMAL])
    assert r.exit_code == 0
    cmd = mock_run.call_args[0][0]
    assert "--set" in cmd and "default" in cmd
    assert "--count" in cmd and "20" in cmd


def test_seed_app_passed_through():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        runner.invoke(cli, ["seed", "--app", "salesforce", "--config", _VALID_MINIMAL])
    cmd = mock_run.call_args[0][0]
    assert "--app" in cmd and "salesforce" in cmd


def test_seed_seed_val_passed_through():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        runner.invoke(cli, ["seed", "--seed", "99", "--config", _VALID_MINIMAL])
    cmd = mock_run.call_args[0][0]
    assert "--seed" in cmd and "99" in cmd


def test_seed_dry_run_no_subprocess():
    with patch("subprocess.run") as mock_run:
        r = runner.invoke(cli, ["seed", "--dry-run", "--config", _VALID_MINIMAL])
    mock_run.assert_not_called()
    assert "Would run:" in r.stdout


def test_seed_verbose_echoes_stdout():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="seeded ok", stderr="")
        r = runner.invoke(cli, ["seed", "--verbose", "--config", _VALID_MINIMAL])
    assert "seeded ok" in r.stdout


def test_seed_subprocess_nonzero_exits_4():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="bad error")
        r = runner.invoke(cli, ["seed", "--config", _VALID_MINIMAL])
    assert r.exit_code == 4


def test_seed_script_not_found_exits_2():
    with patch("src.platform_cli.main._SCRIPTS_DIR", Path("/no/such/dir")):
        r = runner.invoke(cli, ["seed", "--config", _VALID_MINIMAL])
    assert r.exit_code == 2


def test_seed_uses_absolute_script_path():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        runner.invoke(cli, ["seed", "--config", _VALID_MINIMAL])
    cmd = mock_run.call_args[0][0]
    script_arg = cmd[3]
    assert Path(script_arg).is_absolute()


def test_seed_config_defaults_applied(tmp_path):
    cfg = tmp_path / "h.yaml"
    cfg.write_text(
        "cli:\n"
        "  seed:\n"
        "    set: large\n"
        "    count: 50\n"
        "    seed: 7\n"
        "apps:\n"
        "  - id: a\n"
        "    vendor: V\n"
        "    product: P\n"
        "    environments:\n"
        "      dev:\n"
        "        host: a-dev.local\n"
        "    routes:\n"
        "      - id: home\n"
        "        path: /\n"
        "        pattern_type: path\n"
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        runner.invoke(cli, ["seed", "--config", str(cfg)])
    cmd = mock_run.call_args[0][0]
    assert "large" in cmd
    assert "50" in cmd
    assert "7" in cmd


# ---------------------------------------------------------------------------
# idp export / import
# ---------------------------------------------------------------------------


def _mock_token_response():
    resp = MagicMock()
    resp.json.return_value = {"access_token": "test-token"}
    resp.raise_for_status = MagicMock()
    return resp


def _mock_realm_response(realm_data: dict):
    resp = MagicMock()
    resp.json.return_value = realm_data
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    return resp


def test_idp_export_writes_file(tmp_path):
    out = tmp_path / "realm.json"
    realm_data = {"realm": "harness", "id": "harness"}
    with patch("httpx.post", return_value=_mock_token_response()), \
         patch("httpx.get", return_value=_mock_realm_response(realm_data)):
        r = runner.invoke(cli, ["idp", "export", "--out", str(out), "--config", _VALID_MINIMAL])
    assert r.exit_code == 0
    assert out.exists()
    assert json.loads(out.read_text())["realm"] == "harness"


def test_idp_export_api_error_exits_1():
    err_resp = MagicMock()
    err_resp.status_code = 401
    with patch("httpx.post", return_value=_mock_token_response()), \
         patch("httpx.get", side_effect=httpx_status_error(401)):
        r = runner.invoke(cli, ["idp", "export", "--config", _VALID_MINIMAL])
    assert r.exit_code == 1


def test_idp_export_connect_error_exits_1():
    import httpx
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        r = runner.invoke(cli, ["idp", "export", "--config", _VALID_MINIMAL])
    assert r.exit_code == 1


def test_idp_import_post_201_exits_0(tmp_path):
    src = tmp_path / "realm.json"
    src.write_text('{"realm": "harness"}')
    post_resp = MagicMock(status_code=201)
    with patch("httpx.post", side_effect=[_mock_token_response(), post_resp]):
        r = runner.invoke(cli, ["idp", "import", "--src", str(src), "--config", _VALID_MINIMAL])
    assert r.exit_code == 0


def test_idp_import_post_409_put_204_exits_0(tmp_path):
    src = tmp_path / "realm.json"
    src.write_text('{"realm": "harness"}')
    conflict_resp = MagicMock(status_code=409)
    put_resp = MagicMock(status_code=204)
    with patch("httpx.post", side_effect=[_mock_token_response(), conflict_resp]), \
         patch("httpx.put", return_value=put_resp):
        r = runner.invoke(cli, ["idp", "import", "--src", str(src), "--config", _VALID_MINIMAL])
    assert r.exit_code == 0


def test_idp_import_post_409_put_500_exits_1(tmp_path):
    src = tmp_path / "realm.json"
    src.write_text('{"realm": "harness"}')
    conflict_resp = MagicMock(status_code=409)
    put_resp = MagicMock(status_code=500)
    with patch("httpx.post", side_effect=[_mock_token_response(), conflict_resp]), \
         patch("httpx.put", return_value=put_resp):
        r = runner.invoke(cli, ["idp", "import", "--src", str(src), "--config", _VALID_MINIMAL])
    assert r.exit_code == 1


def test_idp_import_src_not_found_exits_2():
    r = runner.invoke(cli, ["idp", "import", "--src", "/no/such/realm.json", "--config", _VALID_MINIMAL])
    assert r.exit_code == 2


def test_idp_import_credentials_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ADMIN_USER", "myadmin")
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASS", "mypass")
    src = tmp_path / "realm.json"
    src.write_text('{"realm": "harness"}')
    post_resp = MagicMock(status_code=201)
    captured = {}
    def _fake_post(url, **kwargs):
        if "token" in url:
            captured.update(kwargs.get("data", {}))
            return _mock_token_response()
        return post_resp
    with patch("httpx.post", side_effect=_fake_post):
        runner.invoke(cli, ["idp", "import", "--src", str(src), "--config", _VALID_MINIMAL])
    assert captured.get("username") == "myadmin"
    assert captured.get("password") == "mypass"


def test_idp_import_keycloak_url_override(tmp_path):
    src = tmp_path / "realm.json"
    src.write_text('{"realm": "harness"}')
    post_resp = MagicMock(status_code=201)
    captured_urls = []
    def _fake_post(url, **kwargs):
        captured_urls.append(url)
        if "token" in url:
            return _mock_token_response()
        return post_resp
    with patch("httpx.post", side_effect=_fake_post):
        runner.invoke(cli, [
            "idp", "import", "--src", str(src),
            "--keycloak-url", "http://custom-kc:8080",
            "--config", _VALID_MINIMAL,
        ])
    assert any("custom-kc:8080" in u for u in captured_urls)


# ---------------------------------------------------------------------------
# idp verify
# ---------------------------------------------------------------------------


def _oidc_ok():
    r = MagicMock()
    r.status_code = 200
    return r


def _clients_ok(client_ids):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = [{"clientId": c} for c in client_ids]
    return r


def test_idp_verify_all_pass():
    with patch("httpx.get", side_effect=[_oidc_ok(), _clients_ok(["browser-client", "service-client"])]), \
         patch("httpx.post", return_value=_mock_token_response()):
        r = runner.invoke(cli, ["idp", "verify", "--no-retry", "--config", _VALID_MINIMAL])
    assert r.exit_code == 0
    assert "[PASS] oidc-discovery" in r.output
    assert "[PASS] clients-present" in r.output


def test_idp_verify_skip_token_check_without_secret():
    with patch("httpx.get", side_effect=[_oidc_ok(), _clients_ok(["browser-client", "service-client"])]), \
         patch("httpx.post", return_value=_mock_token_response()):
        r = runner.invoke(cli, ["idp", "verify", "--no-retry", "--config", _VALID_MINIMAL])
    assert "[SKIP] token-check" in r.output


def test_idp_verify_pass_token_check_with_secret():
    token_resp = MagicMock(status_code=200)
    token_resp.json.return_value = {"access_token": "tok", "access_token2": "tok2"}
    with patch("httpx.get", side_effect=[_oidc_ok(), _clients_ok(["browser-client"])]), \
         patch("httpx.post", side_effect=[_mock_token_response(), token_resp]):
        r = runner.invoke(cli, [
            "idp", "verify", "--no-retry",
            "--client", "browser-client",
            "--client-secret", "mysecret",
            "--config", _VALID_MINIMAL,
        ])
    assert r.exit_code == 0
    assert "[PASS] token-check" in r.output


def test_idp_verify_oidc_404_exits_1():
    fail_resp = MagicMock()
    fail_resp.status_code = 404
    with patch("httpx.get", return_value=fail_resp):
        r = runner.invoke(cli, ["idp", "verify", "--no-retry", "--config", _VALID_MINIMAL])
    assert r.exit_code == 1
    assert "[FAIL]" in r.output


def test_idp_verify_client_missing_exits_1():
    with patch("httpx.get", side_effect=[_oidc_ok(), _clients_ok([])]), \
         patch("httpx.post", return_value=_mock_token_response()):
        r = runner.invoke(cli, [
            "idp", "verify", "--no-retry",
            "--client", "browser-client",
            "--config", _VALID_MINIMAL,
        ])
    assert r.exit_code == 1


def test_idp_verify_connect_error_no_retry_exits_1():
    import httpx
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        r = runner.invoke(cli, ["idp", "verify", "--no-retry", "--config", _VALID_MINIMAL])
    assert r.exit_code == 1


def test_idp_verify_timeout_exits_1():
    import httpx
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")), \
         patch("time.sleep"):
        r = runner.invoke(cli, [
            "idp", "verify", "--timeout", "1", "--retry-interval", "1",
            "--config", _VALID_MINIMAL,
        ])
    assert r.exit_code == 1


def test_idp_verify_custom_clients_checked():
    with patch("httpx.get", side_effect=[_oidc_ok(), _clients_ok(["my-client"])]), \
         patch("httpx.post", return_value=_mock_token_response()):
        r = runner.invoke(cli, [
            "idp", "verify", "--no-retry",
            "--client", "my-client",
            "--config", _VALID_MINIMAL,
        ])
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# run / stop
# ---------------------------------------------------------------------------


def _ok_subprocess():
    return MagicMock(returncode=0, stdout="", stderr="")


def _ok_health():
    resp = MagicMock()
    resp.status_code = 200
    return resp


def test_run_calls_compose_up(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    with patch("subprocess.run", return_value=_ok_subprocess()) as mock_sub, \
         patch("httpx.get", return_value=_ok_health()), \
         patch("src.platform_cli.main._verify_idp"):
        r = runner.invoke(cli, [
            "run", "--compose-file", str(compose),
            "--health-url", "http://localhost:8000/health",
            "--skip-idp-verify",
            "--config", _VALID_MINIMAL,
        ])
    assert r.exit_code == 0
    cmd = mock_sub.call_args[0][0]
    assert "up" in cmd
    assert "--build" in cmd


def test_run_no_build_omits_build_flag(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    with patch("subprocess.run", return_value=_ok_subprocess()) as mock_sub, \
         patch("httpx.get", return_value=_ok_health()):
        runner.invoke(cli, [
            "run", "--compose-file", str(compose),
            "--no-build", "--skip-idp-verify",
            "--config", _VALID_MINIMAL,
        ])
    cmd = mock_sub.call_args[0][0]
    assert "--build" not in cmd


def test_run_project_name_passes_p_flag(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    with patch("subprocess.run", return_value=_ok_subprocess()) as mock_sub, \
         patch("httpx.get", return_value=_ok_health()):
        runner.invoke(cli, [
            "run", "--compose-file", str(compose),
            "--project-name", "myproject", "--skip-idp-verify",
            "--config", _VALID_MINIMAL,
        ])
    cmd = mock_sub.call_args[0][0]
    assert "-p" in cmd and "myproject" in cmd


def test_run_docker_not_installed_exits_3(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    with patch("subprocess.run", side_effect=FileNotFoundError):
        r = runner.invoke(cli, [
            "run", "--compose-file", str(compose), "--skip-idp-verify",
            "--config", _VALID_MINIMAL,
        ])
    assert r.exit_code == 3
    assert "docker not found" in r.output


def test_run_compose_nonzero_exits_3(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="compose error")):
        r = runner.invoke(cli, [
            "run", "--compose-file", str(compose), "--skip-idp-verify",
            "--config", _VALID_MINIMAL,
        ])
    assert r.exit_code == 3


def test_run_health_timeout_exits_3(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    import httpx
    with patch("subprocess.run", return_value=_ok_subprocess()), \
         patch("httpx.get", side_effect=httpx.ConnectError("refused")), \
         patch("time.sleep"), \
         patch("time.monotonic", side_effect=[0, 0, 100]):
        r = runner.invoke(cli, [
            "run", "--compose-file", str(compose),
            "--health-timeout", "30", "--skip-idp-verify",
            "--config", _VALID_MINIMAL,
        ])
    assert r.exit_code == 3


def test_run_skip_idp_verify(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    with patch("subprocess.run", return_value=_ok_subprocess()), \
         patch("httpx.get", return_value=_ok_health()), \
         patch("src.platform_cli.main._verify_idp") as mock_verify:
        runner.invoke(cli, [
            "run", "--compose-file", str(compose),
            "--skip-idp-verify", "--config", _VALID_MINIMAL,
        ])
    mock_verify.assert_not_called()


def test_run_compose_file_missing_exits_2():
    r = runner.invoke(cli, [
        "run", "--compose-file", "/no/such/compose.yml",
        "--config", _VALID_MINIMAL,
    ])
    assert r.exit_code == 2


def test_stop_calls_compose_down(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    with patch("subprocess.run", return_value=_ok_subprocess()) as mock_sub:
        r = runner.invoke(cli, ["stop", "--compose-file", str(compose), "--config", _VALID_MINIMAL])
    assert r.exit_code == 0
    cmd = mock_sub.call_args[0][0]
    assert "down" in cmd


def test_stop_compose_file_missing_exits_2():
    r = runner.invoke(cli, ["stop", "--compose-file", "/no/such.yml", "--config", _VALID_MINIMAL])
    assert r.exit_code == 2


def test_run_config_compose_file_read(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    cfg = tmp_path / "h.yaml"
    cfg.write_text(
        f"cli:\n"
        f"  run:\n"
        f"    compose_file: {compose}\n"
        f"    idp_verify: false\n"
        f"apps:\n"
        f"  - id: a\n"
        f"    vendor: V\n"
        f"    product: P\n"
        f"    environments:\n"
        f"      dev:\n"
        f"        host: a-dev.local\n"
        f"    routes:\n"
        f"      - id: home\n"
        f"        path: /\n"
        f"        pattern_type: path\n"
    )
    with patch("subprocess.run", return_value=_ok_subprocess()), \
         patch("httpx.get", return_value=_ok_health()):
        r = runner.invoke(cli, ["run", "--config", str(cfg)])
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# Helpers used by idp tests
# ---------------------------------------------------------------------------


def httpx_status_error(status_code: int):
    import httpx
    request = httpx.Request("GET", "http://example.com")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


# ---------------------------------------------------------------------------
# Bug-fix regression tests (#62 – #67)
# ---------------------------------------------------------------------------


def test_idp_verify_uses_env_var_credentials(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ADMIN_USER", "myadmin")
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASS", "mypass")
    captured = {}

    def _fake_post(url, **kwargs):
        if "token" in url:
            captured.update(kwargs.get("data", {}))
        return _mock_token_response()

    with patch("httpx.get", side_effect=[_oidc_ok(), _clients_ok(["browser-client", "service-client"])]), \
         patch("httpx.post", side_effect=_fake_post):
        runner.invoke(cli, ["idp", "verify", "--no-retry", "--config", _VALID_MINIMAL])
    assert captured.get("username") == "myadmin"
    assert captured.get("password") == "mypass"


def test_run_phase3_uses_env_var_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("KEYCLOAK_ADMIN_USER", "myadmin")
    monkeypatch.setenv("KEYCLOAK_ADMIN_PASS", "mypass")
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    captured = {}

    def _fake_get_admin_token(base_url, realm, user, pass_):
        captured["user"] = user
        captured["pass_"] = pass_
        return "fake-token"

    with patch("subprocess.run", return_value=_ok_subprocess()), \
         patch("httpx.get", side_effect=[_ok_health(), _oidc_ok(), _clients_ok(["browser-client", "service-client"])]), \
         patch("src.platform_cli.main._get_admin_token", side_effect=_fake_get_admin_token):
        runner.invoke(cli, ["run", "--compose-file", str(compose), "--config", _VALID_MINIMAL])
    assert captured.get("user") == "myadmin"
    assert captured.get("pass_") == "mypass"


def test_idp_verify_timeout_zero_not_default():
    import httpx as _httpx
    with patch("httpx.get", side_effect=_httpx.ConnectError("refused")), \
         patch("time.sleep") as mock_sleep, \
         patch("time.monotonic", return_value=0.0):
        r = runner.invoke(cli, [
            "idp", "verify", "--timeout", "0", "--retry-interval", "1",
            "--config", _VALID_MINIMAL,
        ])
    assert r.exit_code == 1
    mock_sleep.assert_not_called()


def test_run_health_interval_zero_not_default(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    import httpx as _httpx
    with patch("subprocess.run", return_value=_ok_subprocess()), \
         patch("httpx.get", side_effect=[_httpx.ConnectError("refused"), _ok_health()]), \
         patch("time.sleep") as mock_sleep, \
         patch("time.monotonic", return_value=0.0):
        runner.invoke(cli, [
            "run", "--compose-file", str(compose),
            "--health-interval", "0",
            "--health-timeout", "30",
            "--skip-idp-verify",
            "--config", _VALID_MINIMAL,
        ])
    mock_sleep.assert_called_once_with(0)


def test_idp_export_default_out_is_absolute():
    with patch("httpx.post", return_value=_mock_token_response()), \
         patch("httpx.get", return_value=_mock_realm_response({"realm": "harness"})), \
         patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.write_text"):
        r = runner.invoke(cli, ["idp", "export", "--config", _VALID_MINIMAL])
    assert r.exit_code == 0
    line = next((l for l in r.output.splitlines() if "Exported realm" in l), None)
    assert line is not None
    path_str = line.split(" to ")[-1].strip()
    assert Path(path_str).is_absolute()


def test_idp_verify_no_duplicate_pass_on_retry():
    with patch("httpx.get", side_effect=[
               _oidc_ok(), _clients_ok([]),
               _oidc_ok(), _clients_ok(["browser-client", "service-client"]),
            ]), \
         patch("httpx.post", return_value=_mock_token_response()), \
         patch("time.sleep"), \
         patch("time.monotonic", return_value=0.0):
        r = runner.invoke(cli, [
            "idp", "verify",
            "--timeout", "10", "--retry-interval", "1",
            "--client", "browser-client",
            "--client", "service-client",
            "--config", _VALID_MINIMAL,
        ])
    assert r.exit_code == 0
    assert r.output.count("[PASS] oidc-discovery") == 1


def test_generate_caddy_single_blank_line_between_blocks(tmp_path):
    out = tmp_path / "Caddyfile"
    runner.invoke(cli, ["generate-caddy", "--config", _VALID_MINIMAL, "--out", str(out)])
    content = out.read_text()
    assert "\n\n\n" not in content


def test_run_phase3_idp_ready_printed(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("version: '3'")
    with patch("subprocess.run", return_value=_ok_subprocess()), \
         patch("httpx.get", return_value=_ok_health()), \
         patch("src.platform_cli.main._verify_idp"):
        r = runner.invoke(cli, ["run", "--compose-file", str(compose), "--config", _VALID_MINIMAL])
    assert "Phase 3: IdP ready" in r.output
