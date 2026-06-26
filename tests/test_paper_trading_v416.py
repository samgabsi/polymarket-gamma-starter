from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, live_v2, paper_automation
from app.config import APP_VERSION
from app.feature_status import build_feature_status_map, build_stub_burndown_map
from app.main import app


@pytest.fixture(autouse=True)
def isolated_paper_runtime(monkeypatch, tmp_path):
    runtime = tmp_path / "paper_automation"
    monkeypatch.setattr(paper_automation, "PAPER_AUTOMATION_DIR", runtime)
    monkeypatch.setattr(paper_automation, "PAPER_ACCOUNT_PATH", runtime / "account.json")
    monkeypatch.setattr(paper_automation, "PAPER_ORDERS_PATH", runtime / "orders.jsonl")
    monkeypatch.setattr(paper_automation, "PAPER_FILLS_PATH", runtime / "fills.jsonl")
    monkeypatch.setattr(paper_automation, "PAPER_POSITIONS_PATH", runtime / "positions.json")
    monkeypatch.setattr(paper_automation, "PAPER_DECISIONS_PATH", runtime / "decisions.jsonl")
    monkeypatch.setattr(paper_automation, "PAPER_RUNS_PATH", runtime / "runs.jsonl")
    monkeypatch.setattr(paper_automation, "PAPER_AUDIT_PATH", runtime / "audit.jsonl")
    live_dir = tmp_path / "live_v2"
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", live_dir)
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", live_dir / "audit_ledger.jsonl")
    for key in list(paper_automation.os.environ):
        if key.startswith("PAPER_TRADING_"):
            monkeypatch.delenv(key, raising=False)
    yield runtime


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post(
            "/login",
            data={"username": "admin", "password": "test-password-123", "next": "/v3/paper-trading"},
            follow_redirects=False,
        )
        assert response.status_code in {303, 307}
        yield client


def _enable_paper(monkeypatch):
    monkeypatch.setenv("PAPER_TRADING_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_AUTOMATION_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRADING_STARTING_BALANCE", "1000")
    monkeypatch.setenv("PAPER_TRADING_MAX_ORDER_NOTIONAL", "25")
    monkeypatch.setenv("PAPER_TRADING_MAX_DAILY_NOTIONAL", "100")
    monkeypatch.setenv("PAPER_TRADING_MIN_EDGE_PCT", "2")
    monkeypatch.setenv("PAPER_TRADING_MIN_CONFIDENCE", "0.70")
    monkeypatch.setenv("PAPER_TRADING_MAX_SPREAD_BPS", "250")
    monkeypatch.setenv("PAPER_TRADING_MAX_SLIPPAGE_BPS", "150")


def test_v416_version_identity():
    assert APP_VERSION == "4.17.0-real"


def test_v416_paper_trading_default_is_disabled_and_live_safe(authed_client):
    response = authed_client.get("/api/v3/paper/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disabled"
    assert body["config"]["enabled"] is False
    assert body["paper_only"] is True
    assert body["live_execution_used"] is False
    assert body["can_place_real_orders"] is False
    assert body["can_cancel_real_orders"] is False
    assert body["order_submitted"] is False
    assert body["order_cancelled"] is False

    run = authed_client.post("/api/v3/paper/run-once", json={})
    assert run.status_code == 200
    result = run.json()
    assert result["ok"] is False
    assert result["status"] == "disabled"
    assert result["disabled_reason"] == "PAPER_TRADING_ENABLED is false."
    assert result["live_execution_used"] is False
    assert result["real_order_submitted"] is False


def test_v416_run_once_creates_simulated_order_fill_position_and_audit(monkeypatch, authed_client, isolated_paper_runtime):
    _enable_paper(monkeypatch)
    reset = authed_client.post("/api/v3/paper/reset", json={"starting_balance": 1000})
    assert reset.status_code == 200

    candidate = {
        "signal_id": "unit-edge-1",
        "candidate_source": "ai_edge_unit_test",
        "strategy_name": "deterministic_edge_threshold",
        "market_id": "unit-market-1",
        "market_title": "Unit paper market",
        "side": "YES",
        "ask_price": 0.40,
        "bid_price": 0.38,
        "notional": 20,
        "edge_pct": 5.0,
        "confidence": 0.82,
        "spread_bps": 200,
        "slippage_bps": 50,
        "data_age_seconds": 10,
        "data_state": "cached",
        "evidence_quality": "strong",
    }
    response = authed_client.post("/api/v3/paper/run-once", json={"candidates": [candidate]})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "completed"
    assert body["candidates_considered"] == 1
    assert body["paper_trades_placed"] == 1
    assert body["paper_only"] is True
    assert body["live_execution_used"] is False
    assert body["real_order_submitted"] is False
    assert body["real_order_cancelled"] is False
    assert body["orders"][0]["status"] == "simulated_filled"
    assert body["orders"][0]["simulated_fill_price"] > 0.40
    assert body["fills"][0]["fill_model_used"] == "conservative"

    account = authed_client.get("/api/v3/paper/account").json()["account"]
    assert account["available_cash"] < 1000
    positions = authed_client.get("/api/v3/paper/positions").json()
    assert positions["count"] == 1
    assert positions["items"][0]["market_id"] == "unit-market-1"
    assert positions["items"][0]["paper_only"] is True
    decisions = authed_client.get("/api/v3/paper/decisions").json()
    assert decisions["items"][0]["final_action"] == "paper_trade"
    audit_rows = [json.loads(line) for line in (isolated_paper_runtime / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(row["action_type"] == "paper_fill_simulated" for row in audit_rows)
    assert all(row["live_execution_used"] is False for row in audit_rows)


def test_v416_strategy_rejects_low_confidence_stale_and_mismatch_candidates(monkeypatch, authed_client):
    _enable_paper(monkeypatch)
    candidates = [
        {"signal_id": "low", "market_id": "m-low", "market_title": "Low confidence", "side": "YES", "ask_price": 0.5, "notional": 10, "edge_pct": 5, "confidence": 0.10, "data_state": "cached"},
        {"signal_id": "stale", "market_id": "m-stale", "market_title": "Stale data", "side": "YES", "ask_price": 0.5, "notional": 10, "edge_pct": 5, "confidence": 0.90, "data_state": "stale", "data_age_seconds": 9999},
        {"signal_id": "mismatch", "market_id": "m-mismatch", "market_title": "Mismatch", "side": "YES", "ask_price": 0.5, "notional": 10, "edge_pct": 5, "confidence": 0.90, "data_state": "cached", "resolution_mismatch_risk": 0.8},
    ]
    response = authed_client.post("/api/v3/paper/run-once", json={"candidates": candidates})
    assert response.status_code == 200
    body = response.json()
    assert body["paper_trades_placed"] == 0
    assert body["rejected_count"] == 3
    reasons = "\n".join(body["risk_rejections"])
    assert "Confidence" in reasons
    assert "Data state stale" in reasons
    assert "Resolution mismatch" in reasons
    assert body["live_execution_used"] is False


def test_v416_paper_trading_page_and_settings_surface_controls(monkeypatch, authed_client):
    _enable_paper(monkeypatch)
    page = authed_client.get("/v3/paper-trading")
    assert page.status_code == 200
    for text in [
        "Automated Paper Trading",
        "Paper trading only",
        "Run paper strategy once",
        "Recent paper orders and fills",
        "Decision log",
        "PAPER_TRADING_ENABLED",
    ]:
        assert text in page.text
    assert 'action="/v3/paper-trading/run-once"' in page.text
    assert 'action="/v3/paper-trading/reset"' in page.text

    settings_page = authed_client.get("/v3/settings")
    assert settings_page.status_code == 200
    assert "Automated paper trading" in settings_page.text
    assert 'name="setting__paper_trading_min_confidence"' in settings_page.text


def test_v416_feature_readiness_reports_paper_trading_truthfully(monkeypatch):
    monkeypatch.setattr("app.feature_status.settings.paper_trading_enabled", True, raising=False)
    monkeypatch.setattr("app.feature_status.settings.paper_trading_automation_enabled", True, raising=False)
    status = build_feature_status_map()
    rows = {row["feature_id"]: row for row in status["items"]}
    assert rows["paper_trading.engine"]["status"] == "working"
    assert rows["paper_trading.automation"]["status"] == "working"
    assert rows["paper_trading.automation"]["live_disabled"] is True
    assert "paper_only=true" in rows["paper_trading.automation"]["operator_implication"]

    stub = build_stub_burndown_map()
    paper_stub = next(row for row in stub["items"] if row["feature_id"] == "paper_trading.automation_loop")
    assert paper_stub["status"] == "working"
    assert paper_stub["route"] == "/v3/paper-trading"
    assert paper_stub["live_disabled"] is True


def test_v416_invalid_paper_confidence_preference_rejected(authed_client):
    response = authed_client.post("/api/v3/settings", json={"paper_trading_min_confidence": "2.0"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["errors"][0]["key"] == "paper_trading_min_confidence"
    assert "<= 1.0" in body["errors"][0]["error"]
    assert body["live_disabled"] is True
