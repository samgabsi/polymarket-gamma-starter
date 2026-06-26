from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import auth, cross_market_arbitrage
from app.config import APP_VERSION, settings
from app.feature_status import build_feature_status_map, build_stub_burndown_map
from app.main import app


@pytest.fixture(autouse=True)
def isolated_arbitrage_runtime(monkeypatch, tmp_path):
    arb_dir = tmp_path / "cross_market_arbitrage"
    monkeypatch.setattr(cross_market_arbitrage, "ARBITRAGE_RUNTIME_DIR", arb_dir)
    monkeypatch.setattr(cross_market_arbitrage, "ARBITRAGE_AUDIT_PATH", arb_dir / "audit.jsonl")
    monkeypatch.setattr(cross_market_arbitrage, "ARBITRAGE_SCANS_PATH", arb_dir / "scans.jsonl")
    monkeypatch.setattr(settings, "arbitrage_scanner_enabled", False)
    monkeypatch.setattr(settings, "arbitrage_review_only", True)
    monkeypatch.setattr(settings, "arbitrage_fetch_orderbooks", False)
    monkeypatch.setattr(settings, "kalshi_enabled", False)
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/arbitrage"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def _audit_rows() -> list[dict]:
    return [
        json.loads(line)
        for line in cross_market_arbitrage.ARBITRAGE_AUDIT_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_v413_arbitrage_page_surfaces_data_state_and_records_scan_snapshot(authed_client):
    assert APP_VERSION == "4.17.0-real"
    page = authed_client.get("/v3/arbitrage?demo=true&min_margin=1.0&min_confidence=0.72")
    assert page.status_code == 200
    for text in [
        "Data state",
        "sample",
        "Feature readiness",
        "Record scan snapshot",
        "Configured live read",
        "operator implication",
    ]:
        assert text.lower() in page.text.lower()

    recorded = authed_client.post(
        "/v3/arbitrage/scan/record",
        data={
            "demo": "true",
            "min_margin": "1.0",
            "min_confidence": "0.72",
            "return_to": "/v3/arbitrage?demo=true",
            "reason": "Acceptance test scan snapshot.",
        },
        follow_redirects=False,
    )
    assert recorded.status_code in {303, 307}
    assert "action_status=arbitrage_scan_recorded" in recorded.headers["location"]
    assert cross_market_arbitrage.ARBITRAGE_SCANS_PATH.exists()
    assert cross_market_arbitrage.ARBITRAGE_AUDIT_PATH.exists()

    feedback = authed_client.get(recorded.headers["location"])
    assert feedback.status_code == 200
    assert "Arbitrage Scan Recorded" in feedback.text
    rows = _audit_rows()
    assert rows[-1]["action"] == "arbitrage_scan_recorded"
    assert rows[-1]["feature_area"] == "cross_market_arbitrage"
    assert rows[-1]["previous_state"] == "unpersisted_scan_preview"
    assert rows[-1]["new_state"] == "persisted_scan_snapshot"
    assert rows[-1]["source_route"] == "/v3/arbitrage/scan/record"
    assert rows[-1]["data_state"] == "sample"
    assert rows[-1]["review_only"] is True
    assert rows[-1]["live_disabled"] is True
    assert rows[-1]["order_submitted"] is False


def test_v413_arbitrage_scan_api_has_data_state_and_post_record_endpoint(authed_client):
    scan = authed_client.get("/api/v3/arbitrage/scan?demo=true")
    assert scan.status_code == 200
    body = scan.json()
    assert body["scanner_status"] == "disabled"
    assert body["data_state"] == "sample"
    assert body["sample_data"] is True
    assert body["persisted"] is False
    assert body["scanner_readiness"]["next_action"]
    assert set(body["data_state_values"]) == {"live", "cached", "sample", "stale", "unavailable"}
    assert body["venue_statuses"]
    assert {field for field in ["status", "status_class", "data_state", "operator_implication", "next_action"] if field in body["venue_statuses"][0]} == {
        "status",
        "status_class",
        "data_state",
        "operator_implication",
        "next_action",
    }

    recorded = authed_client.post(
        "/api/v3/arbitrage/scan/record",
        json={"demo": True, "min_margin": 1.0, "min_confidence": 0.72, "operator": "api-test"},
    )
    assert recorded.status_code == 200
    payload = recorded.json()
    assert payload["ok"] is True
    assert payload["scan"]["persisted"] is True
    assert payload["scan"]["data_state"] == "sample"
    assert payload["order_submitted"] is False
    assert payload["trade_approved"] is False
    assert payload["live_trading_armed"] is False
    assert cross_market_arbitrage.ARBITRAGE_SCANS_PATH.exists()


def test_v413_arbitrage_review_audit_records_source_and_data_state(authed_client):
    scan = authed_client.get("/api/v3/arbitrage/scan?demo=true").json()
    opportunity_id = scan["items"][0]["opportunity_id"]
    review = authed_client.post(
        f"/v3/arbitrage/opportunity/{opportunity_id}/review",
        data={
            "action": "watchlist",
            "operator_note": "Watch for equivalence review.",
            "data_state": scan["data_state"],
            "data_freshness": scan["data_state"],
            "scan_id": scan["scan_id"],
            "target_name": scan["items"][0]["market_a"]["market_title"],
            "return_to": "/v3/arbitrage?demo=true",
        },
        follow_redirects=False,
    )
    assert review.status_code in {303, 307}
    rows = _audit_rows()
    row = rows[-1]
    assert row["action"] == "watchlist"
    assert row["feature_area"] == "cross_market_arbitrage"
    assert row["action_type"] == "candidate_review_decision"
    assert row["target_id"] == opportunity_id
    assert row["previous_state"] == "candidate_visible_in_scan"
    assert row["new_state"] == "watchlist"
    assert row["source_route"] == "/v3/arbitrage"
    assert row["source_component"] == "cross_market_arbitrage.review_form"
    assert row["data_state"] == "sample"
    assert row["review_only"] is True
    assert row["live_disabled"] is True
    assert row["order_submitted"] is False
    assert row["live_trading_armed"] is False


def test_v413_feature_readiness_schema_has_operator_implication_and_error_status():
    stub = build_stub_burndown_map()
    status = build_feature_status_map()
    assert "error" in stub["status_values"]
    assert "error" in status["status_values"]
    assert stub["data_state_values"] == ["live", "cached", "sample", "stale", "unavailable"]
    assert status["data_state_values"] == stub["data_state_values"]

    required = {"operator_implication", "next_action", "data_state", "safe_review_only", "live_disabled", "reason", "status"}
    for collection in [stub["items"], status["items"]]:
        for row in collection:
            assert required.issubset(row)
            assert row["data_state"] in stub["data_state_values"]

    stub_rows = {row["feature_id"]: row for row in stub["items"]}
    status_rows = {row["feature_id"]: row for row in status["items"]}
    assert stub_rows["arbitrage.scanner_review"]["data_state"] == "sample"
    assert status_rows["arbitrage.scanner"]["data_state"] == "sample"
    assert status_rows["arbitrage.review_actions"]["operator_implication"]
