from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import ai_edge_calibration, ai_edge_research, ai_edge_schemas, ai_evidence, ai_openai_client, ai_prompt_governance, auth
from app.config import APP_VERSION
from app.main import app
from app.navigation_registry import get_route_aliases


@pytest.fixture(autouse=True)
def isolated_edge_runtime(tmp_path, monkeypatch):
    edge_dir = tmp_path / "ai" / "edge"
    ai_dir = tmp_path / "ai"
    monkeypatch.setattr(ai_edge_research, "EDGE_DIR", edge_dir)
    monkeypatch.setattr(ai_edge_research, "RESEARCH_PACKETS_PATH", edge_dir / "research_packets.jsonl")
    monkeypatch.setattr(ai_evidence, "EDGE_DIR", edge_dir)
    monkeypatch.setattr(ai_evidence, "EVIDENCE_SOURCES_PATH", edge_dir / "evidence_sources.jsonl")
    monkeypatch.setattr(ai_edge_calibration, "EDGE_DIR", edge_dir)
    monkeypatch.setattr(ai_edge_calibration, "CALIBRATION_RECORDS_PATH", edge_dir / "calibration_records.jsonl")
    monkeypatch.setattr(ai_openai_client, "AI_DIR", ai_dir)
    monkeypatch.setattr(ai_openai_client, "AI_AUDIT_PATH", ai_dir / "ai_audit.jsonl")
    yield


@pytest.fixture()
def authed_client(monkeypatch, tmp_path):
    users_path = tmp_path / "users.json"
    monkeypatch.setattr(auth, "USERS_PATH", users_path)
    auth.create_user("admin", "test-password-123", "admin")
    with TestClient(app) as client:
        response = client.post("/login", data={"username": "admin", "password": "test-password-123", "next": "/v3/ai/edge"}, follow_redirects=False)
        assert response.status_code in {303, 307}
        yield client


def _edge_payload() -> dict[str, object]:
    return {
        "research_question": "Does the supplied evidence support a research-only edge thesis?",
        "market_id": "EDGE-TEST",
        "market_title": "Validation fake market",
        "evidence_sources": [
            {
                "title": "Validation source A",
                "url": "https://example.com/source-a",
                "snippet": "The validation evidence supports the dry-run research thesis.",
                "claim_stance": "supports",
                "published_at": "2026-06-01",
            },
            {
                "title": "Validation source B",
                "url": "https://example.com/source-b",
                "snippet": "A second validation source is mixed and requires human review.",
                "claim_stance": "mixed",
                "published_at": "2026-06-02",
            },
        ],
        "draft_probability": 0.57,
    }


def test_ai_edge_safe_defaults_and_schema():
    assert APP_VERSION == "4.17.0-real"
    settings = ai_edge_research.edge_settings_summary()
    assert settings["safe_default_posture"] is True
    assert settings["ai_edge_enable"] is False
    assert settings["ai_edge_provider"] == "mock"
    assert settings["ai_edge_dry_run_only"] is True
    assert settings["ai_edge_allow_web_search"] is False
    assert settings["openai_enable_web_search"] is False
    assert settings["local_llm_edge_can_search_web"] is False
    schemas = ai_edge_schemas.schema_registry()
    assert {"AIEdgeEvidenceSource", "AIEdgeResearchPacket", "AIEdgeCalibrationRecord"}.issubset({item["schema_id"] for item in schemas["items"]})


def test_ai_edge_prompt_governance_templates_include_required_safety_language():
    required_categories = {
        "edge_research_packet",
        "evidence_source_summary",
        "contradiction_analysis",
        "missing_information_analysis",
        "market_implied_comparison",
        "edge_calibration_summary",
        "outcome_review",
        "edge_research_export_summary",
    }
    templates = {item["category"]: item for item in ai_prompt_governance.list_prompt_templates()["items"]}
    assert required_categories.issubset(templates)
    for category in required_categories:
        prompt = templates[category]["prompt_preview"].lower()
        assert "not financial advice" in prompt
        assert "not trade approval" in prompt
        assert "no live mutation" in prompt or "must not cause live mutation" in prompt
        assert "do not invent data" in prompt
        assert "source limitations" in prompt
        assert "contradictions" in prompt
        assert "assumptions" in prompt
        assert "citations or source metadata" in prompt


def test_ai_edge_dry_run_packet_is_evidence_backed_no_network():
    generated = ai_edge_research.generate_edge_packet(_edge_payload(), write=True)
    packet = generated["packet"]
    assert packet["packet_evidence_backed"] is True
    assert len(packet["evidence_sources"]) == 2
    assert len(packet["citations"]) == 2
    assert packet["contradictions"]
    assert packet["probability_draft"]["fair_probability"] == 0.57
    assert packet["external_network_called"] is False
    assert packet["ai_model_called"] is False
    assert packet["order_submitted"] is False
    assert packet["no_trade_approval"] is True
    assert packet["local_llm_edge_review"]["local_llm_claimed_web_search"] is False
    assert packet["prompt_metadata"]["raw_prompt_stored"] is False
    assert packet["response_metadata"]["raw_response_stored"] is False
    assert ai_edge_schemas.validate_packet(packet)["ok"] is True
    assert ai_edge_research.list_packets()["count"] == 1
    assert ai_evidence.list_evidence_sources()["count"] == 2
    assert ai_edge_calibration.calibration_summary()["pending_count"] == 1
    assert "sk-test-secret" not in json.dumps(ai_edge_research.export_json()).lower()


def test_ai_edge_web_search_dry_run_is_blocked_by_default():
    result = ai_edge_research.openai_web_search_dry_run({"research_question": "Find current sources", "queries": ["current market evidence"]})
    plan = result["request_plan"]
    packet = result["packet"]
    assert plan["web_search_request_built"] is True
    assert plan["web_search_allowed_now"] is False
    assert any("OPENAI_ENABLE_WEB_SEARCH is false" in blocker for blocker in plan["blockers"])
    assert result["external_network_called"] is False
    assert packet["external_network_called"] is False
    assert packet["openai_web_search"]["web_search_request_built"] is True


def test_ai_edge_calibration_outcome_is_research_only():
    packet = ai_edge_research.generate_edge_packet(_edge_payload(), write=True)["packet"]
    outcome = ai_edge_calibration.record_outcome({"packet_id": packet["packet_id"], "resolved_outcome": True}, write=True)
    record = outcome["record"]
    assert record["status"] == "resolved"
    assert record["outcome_recorded"] is True
    assert record["brier_score"] >= 0
    assert record["no_trade_approval"] is True
    assert record["order_submitted"] is False
    assert ai_edge_calibration.calibration_summary()["resolved_count"] == 1


def test_ai_edge_routes_aliases_and_exports_render(authed_client):
    aliases = get_route_aliases()
    assert aliases["/edge"] == "/v3/ai/edge"
    assert aliases["/edge/new"] == "/v3/ai/edge/new"
    assert aliases["/edge/packets"] == "/v3/ai/edge/packets"
    for route in ["/v3/ai/edge", "/v3/ai/edge/new", "/v3/ai/edge/packets", "/v3/ai/edge/evidence", "/v3/ai/edge/calibration", "/v3/ai/edge/settings"]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "AI Edge Research" in response.text
        assert "supersecret" not in response.text.lower()
    for route in [
        "/api/v3/ai/edge/summary",
        "/api/v3/ai/edge/settings",
        "/api/v3/ai/edge/schemas",
        "/api/v3/ai/edge/packets",
        "/api/v3/ai/edge/evidence",
        "/api/v3/ai/edge/calibration",
        "/api/v3/ai/edge/calibration/summary",
        "/api/v3/ai/edge/export.md",
        "/api/v3/ai/edge/export.csv",
    ]:
        response = authed_client.get(route)
        assert response.status_code == 200, route
        assert "sk-test-secret" not in response.text.lower()
    dry_run = authed_client.post("/api/v3/ai/edge/research/dry-run", json=_edge_payload())
    assert dry_run.status_code == 200
    assert dry_run.json()["packet"]["external_network_called"] is False
    web_dry_run = authed_client.post("/api/v3/ai/edge/openai-web-dry-run", json={"research_question": "Search review"})
    assert web_dry_run.status_code == 200
    assert web_dry_run.json()["request_plan"]["web_search_allowed_now"] is False


def test_ai_edge_market_row_analysis_is_review_only_and_no_live_mutation(authed_client):
    payload = {
        "market_id": "france-world-cup",
        "question": "Will France win the 2026 FIFA World Cup?",
        "outcomes": [{"name": "YES", "price": 0.18}, {"name": "NO", "price": 0.82}],
        "probability_model": {"market_probability": 0.18, "model_probability": 0.205, "confidence": "medium"},
        "volume_24hr": 50000,
        "liquidity": 25000,
        "data_age_minutes": 1,
        "evidence_sources": [{"title": "Fixture", "snippet": "Validation-only evidence", "claim_stance": "mixed"}],
        "write": False,
    }
    response = authed_client.post("/api/v3/ai/edge/market/analyze", json=payload)
    assert response.status_code == 200
    body = response.json()
    recommendation = body["market_recommendation"]
    assert recommendation["recommended_side"] == "YES"
    assert recommendation["side_badge"] == "DRAFT YES EDGE"
    assert body["draft_review_only"] is True
    assert body["order_submitted"] is False
    assert body["order_cancelled"] is False
    assert body["trade_approved"] is False
    assert body["live_trading_armed"] is False
    assert body["no_live_mutation"] is True
    packet = body["packet"]
    assert packet["mode"] == "market_row_analysis"
    assert packet["order_submitted"] is False
    assert packet["order_cancelled"] is False
    assert packet["no_trade_approval"] is True

    summary = authed_client.get("/api/v3/ai/edge/market/france-world-cup/summary")
    assert summary.status_code == 200
    assert summary.json()["legend"]["order_submitted"] is False
    family = authed_client.get("/api/v3/ai/edge/family/fifa_world_cup_2026_winner/summary")
    assert family.status_code == 200
    assert family.json()["favorite_ranking_does_not_imply_edge"] is True or "Favorite" in family.text
