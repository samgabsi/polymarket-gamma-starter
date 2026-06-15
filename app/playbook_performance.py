from __future__ import annotations

import csv
from collections import Counter, defaultdict
from io import StringIO
from typing import Any

from .paper_playbooks import list_playbook_decisions, list_playbooks
from .paper_review import build_review_report


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _round(value: Any, places: int = 4) -> float:
    return round(_safe_float(value), places)


def _guardrail() -> str:
    return "Playbook performance is local paper-review analytics only. It is not investment advice, live trading performance, exchange settlement, or wallet activity."


def _market_has_paper_lifecycle(review: dict[str, Any]) -> bool:
    return any(
        _safe_int(review.get(key)) > 0
        for key in ("buy_count", "sell_count", "settlement_count", "open_position_count")
    )


def _closed_or_active(review: dict[str, Any]) -> bool:
    return str(review.get("lifecycle_status") or "") in {"open", "settled", "closed_by_exit", "entry_only_closed_unknown"}


def _decision_market_title(decision: dict[str, Any], review: dict[str, Any] | None = None) -> str:
    review = review or {}
    fit = decision.get("fit_snapshot") if isinstance(decision.get("fit_snapshot"), dict) else {}
    return str(review.get("question") or fit.get("title") or decision.get("market_id") or "")


def _latest_by_market(decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        mid = str(decision.get("market_id") or "")
        if not mid:
            continue
        ts = str(decision.get("updated_at") or decision.get("created_at") or "")
        previous = latest.get(mid)
        if not previous or ts >= str(previous.get("updated_at") or previous.get("created_at") or ""):
            latest[mid] = decision
    return latest


def _base_row(playbook: dict[str, Any]) -> dict[str, Any]:
    return {
        "playbook_id": str(playbook.get("playbook_id") or "unknown"),
        "playbook_name": str(playbook.get("name") or playbook.get("playbook_id") or "Unknown playbook"),
        "playbook_status": str(playbook.get("status") or "unknown"),
        "recommended_action": str(playbook.get("recommended_action") or "manual_review"),
        "decision_count": 0,
        "unique_market_count": 0,
        "reviewed_market_count": 0,
        "paper_lifecycle_market_count": 0,
        "closed_or_active_market_count": 0,
        "win_count": 0,
        "loss_count": 0,
        "breakeven_count": 0,
        "warning_count": 0,
        "positive_count": 0,
        "simulated_cost": 0.0,
        "simulated_proceeds": 0.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "net_pnl": 0.0,
        "avg_net_pnl_per_lifecycle_market": 0.0,
        "win_rate_percent": 0.0,
        "warning_rate_per_market": 0.0,
        "status_counts": {},
        "lifecycle_counts": {},
        "outcome_counts": {},
        "flag_counts": {},
        "last_decision_at": None,
        "recent_markets": [],
        "guardrail": _guardrail(),
    }


def build_playbook_performance(
    *,
    limit: int = 100,
    playbook_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Aggregate local playbook decisions against the paper review report.

    Financial fields are summed once per unique market per playbook so repeated
    decisions do not duplicate P&L. Decision counts still count every decision.
    """
    decisions = list_playbook_decisions(limit=100000, playbook_id=playbook_id)
    if status:
        wanted = str(status).strip().lower()
        decisions = [row for row in decisions if str(row.get("status") or "").lower() == wanted]

    review_report = build_review_report(limit=100000)
    review_by_market = {str(row.get("market_id")): row for row in review_report.get("items", []) if row.get("market_id")}
    playbooks = {str(row.get("playbook_id")): row for row in list_playbooks()}
    if playbook_id and playbook_id not in playbooks:
        playbooks[str(playbook_id)] = {"playbook_id": str(playbook_id), "name": str(playbook_id), "status": "unknown", "recommended_action": "unknown"}

    grouped_decisions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        grouped_decisions[str(decision.get("playbook_id") or "unknown")].append(decision)

    ids = set(playbooks.keys()) | set(grouped_decisions.keys())
    if playbook_id:
        ids = {str(playbook_id)}

    rows: list[dict[str, Any]] = []
    for pid in sorted(ids):
        playbook = playbooks.get(pid) or {"playbook_id": pid, "name": pid, "status": "unknown", "recommended_action": "unknown"}
        row = _base_row(playbook)
        pb_decisions = grouped_decisions.get(pid, [])
        market_ids = sorted({str(d.get("market_id")) for d in pb_decisions if d.get("market_id")})
        latest = _latest_by_market(pb_decisions)
        status_counts = Counter(str(d.get("status") or "unknown") for d in pb_decisions)
        lifecycle_counts: Counter[str] = Counter()
        outcome_counts: Counter[str] = Counter()
        flag_counts: Counter[str] = Counter()

        row["decision_count"] = len(pb_decisions)
        row["unique_market_count"] = len(market_ids)
        row["status_counts"] = dict(sorted(status_counts.items()))
        row["last_decision_at"] = max((str(d.get("updated_at") or d.get("created_at") or "") for d in pb_decisions), default=None)

        recent_markets: list[dict[str, Any]] = []
        for mid in market_ids:
            review = review_by_market.get(mid, {})
            decision = latest.get(mid, {})
            if review:
                row["reviewed_market_count"] += 1
                lifecycle = str(review.get("lifecycle_status") or "unknown")
                outcome = str(review.get("outcome_label") or "unknown")
                lifecycle_counts.update([lifecycle])
                outcome_counts.update([outcome])
                row["warning_count"] += _safe_int(review.get("warning_count"))
                row["positive_count"] += _safe_int(review.get("positive_count"))
                row["simulated_cost"] += _safe_float(review.get("simulated_cost"))
                row["simulated_proceeds"] += _safe_float(review.get("simulated_proceeds"))
                row["realized_pnl"] += _safe_float(review.get("realized_pnl"))
                row["unrealized_pnl"] += _safe_float(review.get("unrealized_pnl"))
                row["net_pnl"] += _safe_float(review.get("net_pnl"))
                for flag in review.get("discipline_flags") or []:
                    if isinstance(flag, dict):
                        flag_counts.update([str(flag.get("code") or "unknown")])
                if _market_has_paper_lifecycle(review):
                    row["paper_lifecycle_market_count"] += 1
                if _closed_or_active(review):
                    row["closed_or_active_market_count"] += 1
                if outcome == "profitable" and _market_has_paper_lifecycle(review):
                    row["win_count"] += 1
                elif outcome == "loss" and _market_has_paper_lifecycle(review):
                    row["loss_count"] += 1
                elif outcome == "breakeven" and _market_has_paper_lifecycle(review):
                    row["breakeven_count"] += 1
            else:
                lifecycle = "no_local_review"
                outcome = "unknown"
                lifecycle_counts.update([lifecycle])
                outcome_counts.update([outcome])

            recent_markets.append(
                {
                    "market_id": mid,
                    "question": _decision_market_title(decision, review),
                    "decision_status": str(decision.get("status") or ""),
                    "decision_at": str(decision.get("updated_at") or decision.get("created_at") or ""),
                    "lifecycle_status": lifecycle,
                    "outcome_label": outcome,
                    "net_pnl": _round(review.get("net_pnl")) if review else 0.0,
                    "warning_count": _safe_int(review.get("warning_count")) if review else 0,
                    "lesson": str(review.get("lesson") or "No local paper review record for this market yet."),
                }
            )

        lifecycle_denominator = max(1, row["paper_lifecycle_market_count"])
        outcome_denominator = row["win_count"] + row["loss_count"]
        row["simulated_cost"] = _round(row["simulated_cost"])
        row["simulated_proceeds"] = _round(row["simulated_proceeds"])
        row["realized_pnl"] = _round(row["realized_pnl"])
        row["unrealized_pnl"] = _round(row["unrealized_pnl"])
        row["net_pnl"] = _round(row["net_pnl"])
        row["avg_net_pnl_per_lifecycle_market"] = _round(row["net_pnl"] / lifecycle_denominator)
        row["win_rate_percent"] = round((row["win_count"] / outcome_denominator) * 100.0, 2) if outcome_denominator else 0.0
        row["warning_rate_per_market"] = round(row["warning_count"] / max(1, row["reviewed_market_count"]), 2)
        row["lifecycle_counts"] = dict(sorted(lifecycle_counts.items()))
        row["outcome_counts"] = dict(sorted(outcome_counts.items()))
        row["flag_counts"] = dict(flag_counts.most_common(20))
        recent_markets.sort(key=lambda item: str(item.get("decision_at") or ""), reverse=True)
        row["recent_markets"] = recent_markets[:10]
        rows.append(row)

    rows.sort(key=lambda item: (item.get("decision_count", 0), item.get("paper_lifecycle_market_count", 0), abs(_safe_float(item.get("net_pnl")))), reverse=True)
    rows = rows[: max(0, int(limit))]
    return {"summary": summarize_playbook_performance(rows), "items": rows, "guardrail": _guardrail()}


def build_playbook_performance_detail(playbook_id: str) -> dict[str, Any]:
    report = build_playbook_performance(limit=1, playbook_id=playbook_id)
    item = (report.get("items") or [None])[0]
    decisions = list_playbook_decisions(limit=100000, playbook_id=playbook_id)
    return {
        "playbook_id": str(playbook_id),
        "item": item,
        "decisions": decisions,
        "summary": report.get("summary", {}),
        "guardrail": _guardrail(),
    }


def summarize_playbook_performance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    lifecycle_counts: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    for row in rows:
        status_counts.update(row.get("status_counts") or {})
        lifecycle_counts.update(row.get("lifecycle_counts") or {})
        outcome_counts.update(row.get("outcome_counts") or {})
        flag_counts.update(row.get("flag_counts") or {})
    decision_count = sum(_safe_int(row.get("decision_count")) for row in rows)
    market_count = sum(_safe_int(row.get("unique_market_count")) for row in rows)
    lifecycle_market_count = sum(_safe_int(row.get("paper_lifecycle_market_count")) for row in rows)
    wins = sum(_safe_int(row.get("win_count")) for row in rows)
    losses = sum(_safe_int(row.get("loss_count")) for row in rows)
    win_loss_denominator = wins + losses
    return {
        "playbook_count": len(rows),
        "decision_count": decision_count,
        "unique_market_count_sum": market_count,
        "paper_lifecycle_market_count": lifecycle_market_count,
        "status_counts": dict(sorted(status_counts.items())),
        "lifecycle_counts": dict(sorted(lifecycle_counts.items())),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "flag_counts": dict(flag_counts.most_common(20)),
        "simulated_cost": _round(sum(_safe_float(row.get("simulated_cost")) for row in rows)),
        "simulated_proceeds": _round(sum(_safe_float(row.get("simulated_proceeds")) for row in rows)),
        "realized_pnl": _round(sum(_safe_float(row.get("realized_pnl")) for row in rows)),
        "unrealized_pnl": _round(sum(_safe_float(row.get("unrealized_pnl")) for row in rows)),
        "net_pnl": _round(sum(_safe_float(row.get("net_pnl")) for row in rows)),
        "win_count": wins,
        "loss_count": losses,
        "breakeven_count": sum(_safe_int(row.get("breakeven_count")) for row in rows),
        "win_rate_percent": round((wins / win_loss_denominator) * 100.0, 2) if win_loss_denominator else 0.0,
        "warning_count": sum(_safe_int(row.get("warning_count")) for row in rows),
        "positive_count": sum(_safe_int(row.get("positive_count")) for row in rows),
        "guardrail": _guardrail(),
    }


def playbook_performance_to_csv(rows: list[dict[str, Any]]) -> str:
    fields = [
        "playbook_id",
        "playbook_name",
        "playbook_status",
        "recommended_action",
        "decision_count",
        "unique_market_count",
        "reviewed_market_count",
        "paper_lifecycle_market_count",
        "win_count",
        "loss_count",
        "breakeven_count",
        "win_rate_percent",
        "warning_count",
        "positive_count",
        "simulated_cost",
        "simulated_proceeds",
        "realized_pnl",
        "unrealized_pnl",
        "net_pnl",
        "avg_net_pnl_per_lifecycle_market",
        "warning_rate_per_market",
        "last_decision_at",
    ]
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(row))
    return buf.getvalue()
