"""
Tests for GET /manifest endpoint and build_manifest() pure function.
Covers GitHub issue #105 (epic #103).
"""
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.core.config import load_config, load_keycloak_config, parse_data_set
from src.core.manifest import build_manifest, parse_hosts_file
from src.core.models import FAULT_KINDS, App, Environment, Fault, PatternType, Route, ScenarioDefinition


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_HARNESS_YAML = Path(__file__).parent.parent / "harness.yaml"
_HOSTS_FILE = Path(__file__).parent.parent / "infra" / "hosts.txt"
_DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def real_apps():
    return load_config(_HARNESS_YAML)


@pytest.fixture(scope="module")
def real_keycloak():
    return load_keycloak_config(_HARNESS_YAML)


@pytest.fixture(scope="module")
def real_hosts():
    return parse_hosts_file(_HOSTS_FILE)


@pytest.fixture(scope="module")
def real_records(real_apps):
    from src.backend.data_loader import DataLoader
    from src.backend.service import HarnessService, InMemoryChallengeStore, InMemoryScenarioStore
    dataset = parse_data_set(_HARNESS_YAML)
    loader = DataLoader(_DATA_DIR, dataset)
    service = HarnessService(loader, InMemoryChallengeStore(), InMemoryScenarioStore())
    return service.get_all_entity_records(real_apps)


@pytest.fixture(scope="module")
def manifest(real_apps, real_records, real_hosts, real_keycloak):
    return build_manifest(real_apps, real_records, real_hosts, real_keycloak, version="0.1.0")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# parse_hosts_file
# ---------------------------------------------------------------------------

def test_parse_hosts_file_returns_list(real_hosts):
    assert isinstance(real_hosts, list)
    assert len(real_hosts) > 0


def test_parse_hosts_file_entry_shape(real_hosts):
    for entry in real_hosts:
        assert "ip" in entry
        assert "hostname" in entry


def test_parse_hosts_file_skips_comments(real_hosts):
    hostnames = [e["hostname"] for e in real_hosts]
    assert all(not h.startswith("#") for h in hostnames)


def test_parse_hosts_file_includes_known_host(real_hosts):
    hostnames = {e["hostname"] for e in real_hosts}
    assert "salesforce-dev.local" in hostnames


def test_parse_hosts_file_missing_file():
    result = parse_hosts_file(Path("/nonexistent/hosts.txt"))
    assert result == []


# ---------------------------------------------------------------------------
# build_manifest — top-level shape
# ---------------------------------------------------------------------------

def test_manifest_has_required_top_level_keys(manifest):
    assert "version" in manifest
    assert "network" in manifest
    assert "apps" in manifest
    assert "users" in manifest
    assert "idp" in manifest
    assert "fault_injection" in manifest
    assert "active_state" in manifest


def test_manifest_version(manifest):
    assert manifest["version"] == "0.1.0"


def test_manifest_network_hosts(manifest):
    hosts = manifest["network"]["hosts"]
    assert isinstance(hosts, list)
    assert len(hosts) > 0
    hostnames = {h["hostname"] for h in hosts}
    assert "salesforce-dev.local" in hostnames


def test_manifest_network_hosts_file(manifest):
    assert manifest["network"]["hosts_file"] == "infra/hosts.txt"


# ---------------------------------------------------------------------------
# build_manifest — apps / environments
# ---------------------------------------------------------------------------

def test_manifest_apps_nonempty(manifest):
    assert len(manifest["apps"]) > 0


def test_manifest_app_shape(manifest):
    app_entry = manifest["apps"][0]
    assert "id" in app_entry
    assert "vendor" in app_entry
    assert "product" in app_entry
    assert "environments" in app_entry


def test_manifest_env_has_base_url(manifest):
    sf = next(a for a in manifest["apps"] if a["id"] == "salesforce")
    dev = next(e for e in sf["environments"] if e["id"] == "dev")
    assert dev["base_url"] == "http://salesforce-dev.local"


def test_manifest_env_has_routes(manifest):
    sf = next(a for a in manifest["apps"] if a["id"] == "salesforce")
    dev = next(e for e in sf["environments"] if e["id"] == "dev")
    assert len(dev["routes"]) > 0


# ---------------------------------------------------------------------------
# build_manifest — detail route
# ---------------------------------------------------------------------------

def _sf_dev_route(manifest, route_id: str) -> dict:
    sf = next(a for a in manifest["apps"] if a["id"] == "salesforce")
    dev = next(e for e in sf["environments"] if e["id"] == "dev")
    return next(r for r in dev["routes"] if r["id"] == route_id)


def test_detail_route_kind(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert r["kind"] == "detail"


def test_detail_route_supported_methods(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert r["supported_methods"] == ["GET"]


def test_detail_route_url_template_path(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert r["url_template"] == "http://salesforce-dev.local/lightning/r/Account/{id}/view"


def test_detail_route_key_param(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert r["key_param"] == "id"


def test_detail_route_entity(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert r["entity"] == "accounts"


def test_detail_route_record_count(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert r["record_count"] == 20


def test_detail_route_candidates_is_list_of_strings(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert isinstance(r["candidates"], list)
    assert all(isinstance(c, str) for c in r["candidates"])


def test_detail_route_candidates_nonempty(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert len(r["candidates"]) > 0


def test_detail_route_candidate_count_matches(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert r["candidate_count"] == len(r["candidates"])


def test_detail_route_lookup_sources_ranked(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert r["lookup_sources"] == ["api", "html"]


# ---------------------------------------------------------------------------
# build_manifest — QUERY detail route url_template
# ---------------------------------------------------------------------------

def _dyn_dev_route(manifest, route_id: str) -> dict:
    dyn = next(a for a in manifest["apps"] if a["id"] == "dynamics")
    dev = next(e for e in dyn["environments"] if e["id"] == "dev")
    return next(r for r in dev["routes"] if r["id"] == route_id)


def test_query_detail_route_url_template_uses_configured_value(manifest):
    r = _dyn_dev_route(manifest, "account-detail")
    assert "appid=00000000" in r["url_template"]
    assert "pagetype=entityrecord" in r["url_template"]
    assert "{id}" in r["url_template"]
    assert r["url_template"].startswith("http://dynamics-dev.local")


def test_query_detail_placeholder_not_normalized(manifest):
    sap = next(a for a in manifest["apps"] if a["id"] == "sap")
    env = next(e for e in sap["environments"] if e["id"] == "dev")
    shell = next(r for r in env["routes"] if r["id"] == "shell")
    assert "{so}" in shell["url_template"]
    assert "{id}" not in shell["url_template"]


# ---------------------------------------------------------------------------
# build_manifest — list route
# ---------------------------------------------------------------------------

def test_list_route_kind(manifest):
    r = _sf_dev_route(manifest, "account-list")
    assert r["kind"] == "list"


def test_list_route_has_url_not_url_template(manifest):
    r = _sf_dev_route(manifest, "account-list")
    assert "url" in r
    assert "url_template" not in r


def test_list_route_url(manifest):
    r = _sf_dev_route(manifest, "account-list")
    assert r["url"] == "http://salesforce-dev.local/lightning/r/Account/list/view"


def test_list_route_entity(manifest):
    r = _sf_dev_route(manifest, "account-list")
    assert r["entity"] == "accounts"


def test_list_route_no_candidates(manifest):
    r = _sf_dev_route(manifest, "account-list")
    assert "candidates" not in r


# ---------------------------------------------------------------------------
# build_manifest — template-only route
# ---------------------------------------------------------------------------

def test_template_only_route_kind(manifest):
    sf = next(a for a in manifest["apps"] if a["id"] == "salesforce")
    dev = next(e for e in sf["environments"] if e["id"] == "dev")
    template_only = next((r for r in dev["routes"] if r["kind"] == "template-only"), None)
    assert template_only is not None


def test_template_only_route_has_url(manifest):
    sf = next(a for a in manifest["apps"] if a["id"] == "salesforce")
    dev = next(e for e in sf["environments"] if e["id"] == "dev")
    template_only = next(r for r in dev["routes"] if r["kind"] == "template-only")
    assert "url" in template_only


# ---------------------------------------------------------------------------
# build_manifest — lookup_sources
# ---------------------------------------------------------------------------

def test_lookup_sources_api_only_for_data_only_route():
    route = Route(id="r", path="/x", pattern_type=PatternType.PATH,
                  data_entity="items", template="")
    app_obj = App(id="a", vendor="V", product="P",
                  environments={"dev": Environment(host="a.local")},
                  routes=[route])
    records = {("a", "items"): [{"id": "1"}]}
    m = build_manifest([app_obj], records, [], {})
    r = m["apps"][0]["environments"][0]["routes"][0]
    assert r["lookup_sources"] == ["api"]


def test_lookup_sources_html_only_for_template_only_route():
    route = Route(id="r", path="/x", pattern_type=PatternType.PATH, template="tmpl")
    app_obj = App(id="a", vendor="V", product="P",
                  environments={"dev": Environment(host="a.local")},
                  routes=[route])
    m = build_manifest([app_obj], {}, [], {})
    r = m["apps"][0]["environments"][0]["routes"][0]
    assert r["lookup_sources"] == ["html"]


def test_lookup_sources_api_preferred_when_both_present(manifest):
    r = _sf_dev_route(manifest, "account-detail")
    assert r["lookup_sources"][0] == "api"


# ---------------------------------------------------------------------------
# build_manifest — fault_injection
# ---------------------------------------------------------------------------

def test_fault_kinds_derived_from_constant(manifest):
    fk = manifest["fault_injection"]["fault_kinds"]
    for kind, spec in FAULT_KINDS.items():
        assert kind in fk
        assert fk[kind]["http_status"] == spec["http_status"]
        assert fk[kind]["retriable"] == spec["retriable"]


def test_fault_injection_has_precedence(manifest):
    prec = manifest["fault_injection"]["precedence"]
    assert isinstance(prec, list)
    assert len(prec) == 4


def test_fault_injection_has_on_request_n_doc(manifest):
    assert "on_request_n" in manifest["fault_injection"]


# ---------------------------------------------------------------------------
# build_manifest — scenarios
# ---------------------------------------------------------------------------

def _sf_dev_scenario(manifest, name: str) -> dict:
    sf = next(a for a in manifest["apps"] if a["id"] == "salesforce")
    dev = next(e for e in sf["environments"] if e["id"] == "dev")
    return next(s for s in dev["scenarios"] if s["name"] == name)


def test_scenario_has_three_activation_methods(manifest):
    s = _sf_dev_scenario(manifest, "session-expired")
    methods = {a["method"] for a in s["activation"]}
    assert methods == {"persistent", "per_request_header", "route_challenge"}


def test_auth_scenario_has_www_authenticate_in_effect(manifest):
    s = _sf_dev_scenario(manifest, "session-expired")
    assert "response_headers" in s["effect"]
    assert s["effect"]["response_headers"]["WWW-Authenticate"] == 'Bearer realm="harness"'


def test_non_auth_scenario_no_response_headers(manifest):
    s = _sf_dev_scenario(manifest, "rate-limited")
    assert "response_headers" not in s["effect"]


def test_scenario_persistent_activation_has_set_clear(manifest):
    s = _sf_dev_scenario(manifest, "session-expired")
    p = next(a for a in s["activation"] if a["method"] == "persistent")
    assert p["set"]["method"] == "PUT"
    assert p["clear"]["method"] == "DELETE"


def test_scenario_per_request_header(manifest):
    s = _sf_dev_scenario(manifest, "session-expired")
    h = next(a for a in s["activation"] if a["method"] == "per_request_header")
    assert h["header"] == "X-Harness-Scenario"
    assert h["value"] == "session-expired"


# ---------------------------------------------------------------------------
# build_manifest — users
# ---------------------------------------------------------------------------

def test_users_list_nonempty(manifest):
    assert len(manifest["users"]) > 0


def test_users_shape(manifest):
    for u in manifest["users"]:
        assert "username" in u
        assert "email" in u
        assert "roles" in u
        assert "password" in u
        assert "password_source" in u


def test_users_default_password_source_when_env_not_set(manifest):
    analyst = next(u for u in manifest["users"] if u["username"] == "analyst")
    assert analyst["password_source"] == "default"
    assert analyst["password"] == "analyst"


def test_users_env_password_source_when_env_set():
    keycloak = {
        "users": [{"username": "analyst", "password_env": "TEST_PASS_VAR", "roles": ["analyst"]}]
    }
    with patch.dict("os.environ", {"TEST_PASS_VAR": "secret123"}):
        m = build_manifest([], {}, [], keycloak)
    u = m["users"][0]
    assert u["password_source"] == "env"
    assert u["password"] == "<env:TEST_PASS_VAR>"


# ---------------------------------------------------------------------------
# build_manifest — idp
# ---------------------------------------------------------------------------

def test_idp_realm(manifest):
    assert manifest["idp"]["realm"] == "harness"


def test_idp_urls(manifest):
    assert "token_url" in manifest["idp"]
    assert "auth_url" in manifest["idp"]
    assert "idp.local" in manifest["idp"]["token_url"]


def test_idp_empty_when_no_keycloak():
    m = build_manifest([], {}, [], {})
    assert m["idp"] == {}


# ---------------------------------------------------------------------------
# GET /manifest endpoint (integration)
# ---------------------------------------------------------------------------

def test_manifest_endpoint_returns_200(client):
    r = client.get("/manifest")
    assert r.status_code == 200


def test_manifest_endpoint_content_type(client):
    r = client.get("/manifest")
    assert "application/json" in r.headers["content-type"]


def test_manifest_endpoint_has_version(client):
    r = client.get("/manifest")
    data = r.json()
    assert "version" in data


def test_manifest_endpoint_has_apps(client):
    r = client.get("/manifest")
    data = r.json()
    assert "apps" in data
    assert len(data["apps"]) > 0


def test_manifest_endpoint_has_network_hosts(client):
    r = client.get("/manifest")
    data = r.json()
    assert "network" in data
    assert "hosts" in data["network"]


def test_manifest_not_caught_by_catch_all(client):
    r = client.get("/manifest", headers={"host": "harness.local"})
    assert r.status_code == 200
    assert "apps" in r.json()
