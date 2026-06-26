from __future__ import annotations

import json

import pytest

from app import live_v2


@pytest.fixture(autouse=True)
def isolated_live_v2(tmp_path, monkeypatch):
    monkeypatch.setattr(live_v2, "LIVE_V2_DIR", tmp_path)
    monkeypatch.setattr(live_v2, "AUDIT_JSONL_PATH", tmp_path / "audit_ledger.jsonl")
    for key in [
        "POLYMARKET_V2_TRADING_MODE",
        "READ_ONLY",
        "POLYMARKET_LIVE_KILL_SWITCH",
        "POLYMARKET_LIVE_ALLOW_REAL_NETWORK",
        "POLYMARKET_LIVE_ENABLE_SUBMIT",
        "POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED",
        "POLYMARKET_LIVE_ENABLE_CANCEL",
        "POLYMARKET_LIVE_MANUAL_CANCEL_ENABLED",
        "POLYMARKET_LIVE_MAX_ORDER_NOTIONAL",
        "POLYMARKET_LIVE_MAX_DAILY_NOTIONAL",
        "POLYMARKET_LIVE_MAX_OPEN_ORDERS",
        "POLYMARKET_PRIVATE_KEY",
        "POLYMARKET_CLOB_API_KEY",
        "POLYMARKET_CLOB_SECRET",
        "POLYMARKET_CLOB_PASSPHRASE",
        "POLYMARKET_V2_CONFIRMATION_PHRASE",
    ]:
        monkeypatch.delenv(key, raising=False)
    yield


def sample_ticket(**overrides):
    payload = {
        "market_id": "market-1",
        "token_id": "1234567890",
        "side": "BUY",
        "order_type": "GTC",
        "price": 0.25,
        "size": 10,
        "human_approval": True,
        "acknowledge_warnings": True,
        "confirmation_phrase": "LIVE ORDER APPROVED",
    }
    payload.update(overrides)
    return payload


def test_default_readiness_is_blocked_fail_closed():
    readiness = live_v2.build_live_v2_readiness()
    assert readiness["overall_status"] == "blocked"
    assert readiness["config"]["trading_mode"] == "research_only"
    assert readiness["config"]["kill_switch_active"] is True
    assert readiness["secret_values_returned"] is False


def test_ticket_preview_blocks_under_default_safe_posture():
    preview = live_v2.build_live_v2_ticket_preview(sample_ticket())
    assert preview["recorded"] is False
    assert preview["risk"]["status"] == "blocked"
    names = {row["name"] for row in preview["risk"]["failures"]}
    assert "kill_switch_clear" in names
    assert "live_mode_armed" in names
    assert "submit_gate_enabled" in names
    rows = live_v2.list_audit_records()
    assert rows and rows[0]["action"] == "ticket_preview"


def test_submit_blocks_before_network_when_confirmation_mismatch(monkeypatch):
    monkeypatch.setenv("POLYMARKET_V2_TRADING_MODE", "live_trading_armed")
    monkeypatch.setenv("READ_ONLY", "false")
    monkeypatch.setenv("POLYMARKET_LIVE_KILL_SWITCH", "false")
    monkeypatch.setenv("POLYMARKET_LIVE_ALLOW_REAL_NETWORK", "true")
    monkeypatch.setenv("POLYMARKET_LIVE_ENABLE_SUBMIT", "true")
    monkeypatch.setenv("POLYMARKET_LIVE_MANUAL_SUBMIT_ENABLED", "true")
    monkeypatch.setenv("POLYMARKET_LIVE_MAX_ORDER_NOTIONAL", "100")
    monkeypatch.setenv("POLYMARKET_LIVE_MAX_DAILY_NOTIONAL", "500")
    monkeypatch.setenv("POLYMARKET_LIVE_MAX_OPEN_ORDERS", "5")
    result = live_v2.submit_live_v2_order(sample_ticket(confirmation_phrase="WRONG"))
    assert result["status"] == "blocked_by_confirmation"
    assert result["network_attempted"] is False


def test_secret_redaction(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "dummy-redaction-token")
    redacted = live_v2.redact_data({"message": "value dummy-redaction-token", "private_key": "dummy-redaction-token"})
    assert "dummy-redaction-token" not in json.dumps(redacted)
    assert redacted["private_key"] == "[redacted]"


def test_audit_csv_export_contains_headers():
    live_v2.record_audit("unit_test", "ok", details={"hello": "world"})
    csv_text = live_v2.audit_to_csv()
    assert "timestamp,app_version,mode,action,status" in csv_text
    assert "unit_test" in csv_text


def test_cancel_blocks_without_required_gates():
    result = live_v2.cancel_live_v2_order({"order_id": "abc", "reason": "test", "confirmation_phrase": "LIVE ORDER APPROVED"})
    assert result["status"] == "blocked"
    assert result["network_attempted"] is False
    assert any("Cancel gates" in item or "Kill switch" in item for item in result["blockers"])


def test_ui_preferences_schema_excludes_sensitive_values():
    schema = live_v2.build_live_v2_preferences_schema()
    assert schema["version"] == "4.17.0-real"
    assert schema["secret_values_allowed"] is False
    assert schema["sensitive_data_allowed"] is False
    keys = {item["key"] for item in schema["preferences"]}
    assert {"table_page_size", "compact_mode", "default_market_query"}.issubset(keys)


def test_audit_filtering_limits_and_filters_rows():
    live_v2.record_audit("ticket_preview", "blocked", details={"market": "abc"})
    live_v2.record_audit("emergency_control", "recorded", details={"note": "kill switch"})
    rows = live_v2.filter_live_v2_audit_records(action="emergency", search="kill", limit=10)
    assert len(rows) == 1
    assert rows[0]["action"] == "emergency_control"
