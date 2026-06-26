from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_governance, live_monitoring, live_portfolio, live_research, live_strategy, live_v2
from app.config import APP_VERSION
from app.main import app


@pytest.fixture(autouse=True)
def isolated_governance(tmp_path, monkeypatch):
    live_dir = tmp_path / "live_v2"
    strategy_dir = tmp_path / "strategy"
    research_dir = tmp_path / "research"
    monitoring_dir = tmp_path / "monitoring"
    portfolio_dir = tmp_path / "portfolio"
    governance_dir = tmp_path / "governance"
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
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v2-live/governance"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def test_version_is_v2_8():
    assert APP_VERSION == "4.17.0-real"


def test_governance_crud_exports_and_safety():
    journal = live_governance.create_journal_entry({"decision_title": "No trade", "decision_type": "no_trade_decision", "confidence_level": 80, "decision_summary": "Wait for evidence."})
    assert journal["ok"] is True
    assert journal["order_submitted"] is False
    jid = journal["item"]["id"]
    edited = live_governance.update_journal_entry(jid, {"status": "reviewed"})
    assert edited["ok"] is True
    checklist = live_governance.create_checklist({"checklist_title": "Pre-trade", "no_trade_alternative_considered": True})
    assert checklist["item"]["total_count"] >= 10
    cid = checklist["item"]["id"]
    completed = live_governance.update_checklist(cid, {"status": "completed"})
    assert completed["ok"] is True
    review = live_governance.create_review({"review_title": "Post trade", "review_type": "post_trade", "lesson_learned": "Follow checklist."})
    assert review["ok"] is True
    daily = live_governance.create_review({"review_title": "Daily", "review_type": "daily", "decisions_made": "One no-trade decision."})
    weekly = live_governance.create_review({"review_title": "Weekly", "review_type": "weekly", "recurring_patterns": "none"})
    rule = live_governance.create_rule({"rule_title": "Require thesis", "severity": "critical"})
    near = live_governance.create_near_miss({"title": "Almost skipped evidence review", "severity": "warning", "money_was_at_risk": False})
    mistake = live_governance.create_mistake_pattern({"pattern_title": "Relied on stale evidence", "pattern_type": "relied_on_stale_evidence", "frequency": 2})
    assert all(item["order_submitted"] is False for item in [daily, weekly, rule, near, mistake])
    exported = live_governance.governance_export_json()
    assert exported["summary"]["journal_entries"] >= 1
    assert "Governance / Decision Journal Export" in live_governance.governance_export_markdown()
    assert "decision_title" in live_governance.governance_csv("journal")
    assert "checklist_title" in live_governance.governance_csv("checklists")
    assert "pattern_title" in live_governance.governance_csv("mistakes")


def test_governance_actions_create_audit_events():
    live_governance.create_journal_entry({"decision_title": "Audit me"})
    live_governance.create_checklist({"checklist_title": "Audit checklist"})
    rows = live_v2.list_audit_records()
    assert any(row["action"].startswith("governance_journal_entry_created") for row in rows)
    assert any(row["action"].startswith("governance_pre_trade_checklist_created") for row in rows)


def test_governance_routes_and_api_endpoints(authed_client):
    page = authed_client.get("/v2-live/governance")
    assert page.status_code == 200
    assert "Governance / Decision Journal" in page.text
    assert "v4.7.0-real" in page.text
    assert authed_client.get("/api/v2/live/governance").status_code == 200
    journal = authed_client.post("/api/v2/live/governance/journal", json={"decision_title": "API journal", "decision_type": "risk_decision"})
    assert journal.status_code == 200
    jid = journal.json()["item"]["id"]
    assert authed_client.post(f"/api/v2/live/governance/journal/{jid}", json={"status": "closed"}).status_code == 200
    checklist = authed_client.post("/api/v2/live/governance/checklists", json={"checklist_title": "API checklist"})
    assert checklist.status_code == 200
    cid = checklist.json()["item"]["id"]
    assert authed_client.post(f"/api/v2/live/governance/checklists/{cid}", json={"status": "completed"}).status_code == 200
    review = authed_client.post("/api/v2/live/governance/reviews", json={"review_title": "API review", "review_type": "daily"})
    assert review.status_code == 200
    rid = review.json()["item"]["id"]
    assert authed_client.post(f"/api/v2/live/governance/reviews/{rid}", json={"status": "completed"}).status_code == 200
    rule = authed_client.post("/api/v2/live/governance/rules", json={"rule_title": "API rule"})
    assert rule.status_code == 200
    rule_id = rule.json()["item"]["id"]
    assert authed_client.post(f"/api/v2/live/governance/rules/{rule_id}", json={"status": "disabled"}).status_code == 200
    assert authed_client.post("/api/v2/live/governance/near-misses", json={"title": "API near miss"}).status_code == 200
    mistake = authed_client.post("/api/v2/live/governance/mistake-patterns", json={"pattern_title": "API mistake"})
    assert mistake.status_code == 200
    mid = mistake.json()["item"]["id"]
    assert authed_client.post(f"/api/v2/live/governance/mistake-patterns/{mid}", json={"status": "resolved"}).status_code == 200
    for endpoint in [
        "/api/v2/live/governance/journal",
        "/api/v2/live/governance/checklists",
        "/api/v2/live/governance/reviews",
        "/api/v2/live/governance/rules",
        "/api/v2/live/governance/near-misses",
        "/api/v2/live/governance/mistake-patterns",
        "/api/v2/live/governance/export.json",
        "/api/v2/live/governance/export.md",
        "/api/v2/live/governance/export/journal.csv",
        "/api/v2/live/governance/export/checklists.csv",
        "/api/v2/live/governance/export/mistakes.csv",
    ]:
        assert authed_client.get(endpoint).status_code == 200, endpoint


def test_governance_exports_redact_secrets(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "governance-secret-token")
    live_governance.create_journal_entry({"decision_title": "governance-secret-token", "reasoning": "governance-secret-token"})
    exported = json.dumps(live_governance.governance_export_json())
    assert "governance-secret-token" not in exported
    assert "governance-secret-token" not in live_governance.governance_export_markdown()


def test_existing_routes_and_gates_still_render_and_block(authed_client):
    for route in ["/v2-live/portfolio", "/v2-live/monitoring", "/v2-live/research", "/v2-live/strategy"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
    submit = authed_client.post("/api/v2/live/order/submit", json={"mode": "live_trading_armed", "side": "BUY", "price": 0.5, "size": 1})
    assert submit.status_code == 200
    assert submit.json().get("network_attempted") is False
    assert submit.json().get("status") in {"blocked_by_risk", "blocked_by_confirmation", "blocked"}
