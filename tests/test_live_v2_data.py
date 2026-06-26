from __future__ import annotations

import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app import auth, live_data, live_governance, live_monitoring, live_portfolio, live_research, live_strategy, live_v2
from app.config import APP_VERSION
from app.main import app


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    live_dir = tmp_path / "live_v2"
    strategy_dir = live_dir / "strategy"
    research_dir = live_dir / "research"
    monitoring_dir = live_dir / "monitoring"
    portfolio_dir = live_dir / "portfolio"
    governance_dir = live_dir / "governance"
    data_dir = live_dir / "data_integrity"
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", live_dir)
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", live_dir / "audit_ledger.jsonl")
    monkeypatch.setattr(live_strategy, "STRATEGY_DIR", strategy_dir)
    monkeypatch.setattr(live_strategy, "STRATEGY_EVENTS_PATH", strategy_dir / "strategy_events.jsonl")
    monkeypatch.setattr(live_research, "RESEARCH_DIR", research_dir)
    monkeypatch.setattr(live_research, "RESEARCH_EVENTS_PATH", research_dir / "research_events.jsonl")
    monkeypatch.setattr(live_monitoring, "MONITORING_DIR", monitoring_dir)
    monkeypatch.setattr(live_monitoring, "MONITORING_EVENTS_PATH", monitoring_dir / "monitoring_events.jsonl")
    monkeypatch.setattr(live_portfolio, "PORTFOLIO_DIR", portfolio_dir)
    monkeypatch.setattr(live_portfolio, "PORTFOLIO_EVENTS_PATH", portfolio_dir / "portfolio_events.jsonl")
    monkeypatch.setattr(live_governance, "GOVERNANCE_DIR", governance_dir)
    monkeypatch.setattr(live_governance, "GOVERNANCE_EVENTS_PATH", governance_dir / "governance_events.jsonl")
    monkeypatch.setattr(live_data, "RUNTIME_ROOT", live_dir)
    monkeypatch.setattr(live_data, "DATA_LAYER_DIR", data_dir)
    monkeypatch.setattr(live_data, "BACKUP_DIR", data_dir / "backups")
    monkeypatch.setattr(live_data, "EXPORT_DIR", data_dir / "exports")
    monkeypatch.setattr(live_data, "REPORT_DIR", data_dir / "reports")
    monkeypatch.setattr(live_data, "DATA_EVENTS_PATH", data_dir / "data_events.jsonl")
    monkeypatch.setattr(live_data, "SUBSYSTEM_PATHS", {
        "audit": live_dir / "audit_ledger.jsonl",
        "strategy": strategy_dir,
        "research": research_dir,
        "monitoring": monitoring_dir,
        "portfolio": portfolio_dir,
        "governance": governance_dir,
        "settings": live_dir / "settings",
    })
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v2-live/data"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_version_is_v2_9():
    assert APP_VERSION == "4.17.0-real"


def test_inventory_health_invalid_json_secret_scan_and_audit(monkeypatch):
    live_strategy.create_thesis({"market_title": "Data test", "market_id": "m1", "thesis_summary": "safe"})
    bad_dir = live_data.SUBSYSTEM_PATHS["settings"]
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "bad.json").write_text("{not-json", encoding="utf-8")
    inv = live_data.runtime_inventory()
    assert inv["count"] >= 1
    health = live_data.run_health_check(deep=True)
    assert health["summary"]["fail"] >= 1
    assert any(check["check_name"] == "json_valid" and check["status"] == "fail" for check in health["checks"])
    fake_secret = "FAKE_TEST_SECRET_DO_NOT_USE"
    monkeypatch.setenv("POLYMARKET_FAKE_API_KEY", fake_secret)
    (bad_dir / "secret.txt").write_text("api_key=" + fake_secret, encoding="utf-8")
    scan = live_data.scan_secrets(paths=[str(bad_dir)])
    dumped = json.dumps(scan)
    assert scan["finding_count"] >= 1
    assert fake_secret not in dumped
    rows = live_v2.list_audit_records()
    assert any(row["action"].startswith("data_data_health_check_run") for row in rows)
    assert any(row["action"].startswith("data_secret_scan_run") for row in rows)


def test_backup_restore_import_export_migration_reports_and_safety():
    live_governance.create_journal_entry({"decision_title": "Back me up"})
    backup = live_data.create_backup_bundle({"name": "unit_backup", "subsystems": ["governance"], "redacted": True})
    assert backup["ok"] is True
    assert backup["order_submitted"] is False
    path = backup["bundle_path"]
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    assert manifest["app_version"] == "4.17.0-real"
    assert manifest["redaction_policy"] == "default_redacted_excludes_secrets"
    validation = live_data.validate_backup_bundle({"bundle_path": path})
    assert validation["ok"] is True
    preview = live_data.restore_preview({"bundle_path": path})
    assert preview["ok"] is True
    blocked = live_data.restore_apply({"bundle_path": path})
    assert blocked["ok"] is False
    restored = live_data.restore_apply({"bundle_path": path, "confirmation": "RESTORE DATA"})
    assert restored["ok"] is True
    export = live_data.export_bundle({"name": "unit_export", "subsystems": "governance"})
    assert export["ok"] is True
    ipreview = live_data.import_preview({"bundle_path": export["bundle_path"]})
    assert ipreview["ok"] is True
    iblocked = live_data.import_apply({"bundle_path": export["bundle_path"]})
    assert iblocked["ok"] is False
    assert live_data.import_apply({"bundle_path": export["bundle_path"], "confirmation": "IMPORT DATA"})["ok"] is True
    registry = live_data.migration_registry()
    assert registry["migration_needed"] is False
    dry = live_data.migration_dry_run({})
    assert dry["mutation_performed"] is False
    assert live_data.migration_apply({})["ok"] is False
    assert live_data.migration_apply({"confirmation": "APPLY MIGRATION"})["ok"] is True
    assert "Data Integrity / Recovery Report" in live_data.recovery_report_markdown()
    assert "check_name" in live_data.checks_csv()


def test_data_routes_and_api_endpoints(authed_client):
    page = authed_client.get("/v2-live/data")
    assert page.status_code == 200
    assert "Data Integrity / Backup / Recovery" in page.text
    assert "v4.7.0-real" in page.text
    for endpoint in [
        "/api/v2/live/data",
        "/api/v2/live/data/health",
        "/api/v2/live/data/inventory",
        "/api/v2/live/data/secrets/scan",
        "/api/v2/live/data/backups",
        "/api/v2/live/data/migrations",
        "/api/v2/live/data/reports/health.json",
        "/api/v2/live/data/reports/health.md",
        "/api/v2/live/data/reports/recovery.json",
        "/api/v2/live/data/reports/recovery.md",
        "/api/v2/live/data/reports/checks.csv",
    ]:
        assert authed_client.get(endpoint).status_code == 200, endpoint
    assert authed_client.post("/api/v2/live/data/health/run", json={"deep": False}).status_code == 200
    backup = authed_client.post("/api/v2/live/data/backup", json={"name": "api_backup", "subsystems": ["governance"]})
    assert backup.status_code == 200
    path = backup.json()["bundle_path"]
    assert authed_client.post("/api/v2/live/data/backup/validate", json={"bundle_path": path}).status_code == 200
    assert authed_client.post("/api/v2/live/data/restore/preview", json={"bundle_path": path}).status_code == 200
    blocked = authed_client.post("/api/v2/live/data/restore/apply", json={"bundle_path": path})
    assert blocked.status_code == 200
    assert blocked.json()["ok"] is False
    export = authed_client.post("/api/v2/live/data/export", json={"name": "api_export", "subsystems": ["governance"]})
    assert export.status_code == 200
    export_path = export.json()["bundle_path"]
    assert authed_client.post("/api/v2/live/data/import/preview", json={"bundle_path": export_path}).status_code == 200
    assert authed_client.post("/api/v2/live/data/import/apply", json={"bundle_path": export_path}).json()["ok"] is False
    assert authed_client.post("/api/v2/live/data/migrations/dry-run", json={}).status_code == 200
    assert authed_client.post("/api/v2/live/data/migrations/apply", json={}).json()["ok"] is False


def test_data_workflows_do_not_place_cancel_or_arm():
    backup = live_data.create_backup_bundle({"name": "safety"})
    export = live_data.export_bundle({"name": "safety_export"})
    dry = live_data.migration_dry_run({})
    for result in [backup, export, dry]:
        assert result["order_submitted"] is False
        assert result["order_cancelled"] is False
        assert result.get("live_trading_armed", False) is False
    submit = live_v2.submit_live_v2_order({"market_id": "m", "token_id": "t", "side": "BUY", "price": 0.5, "size": 1})
    assert submit["status"].startswith("blocked")
    assert submit["network_attempted"] is False


def test_existing_routes_still_render(authed_client):
    for route in ["/v2-live/governance", "/v2-live/portfolio", "/v2-live/monitoring", "/v2-live/research", "/v2-live/strategy"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
