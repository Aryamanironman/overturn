"""Deterministic appeal-strength score and counterfactuals.

No LLM is involved in this module. The formula and cap are documented in
APPEAL_SCORE.md.
"""

from __future__ import annotations

from datetime import date
from typing import Any

COUNTERFACTUAL_SOURCES = [
    "policy_clauses",
    "medical_records",
    "procedure_codes",
    "eob",
    "icd10_codes",
]

DEPENDENCIES = {
    "wrong_clause": {"policy_clauses"},
    "code_mismatch": {"procedure_codes", "icd10_codes"},
    "medical_necessity": {"medical_records"},
    "missing_document": {"claim_documents"},
}


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def bucket_for(score: int) -> str:
    if score >= 85:
        return "strong"
    if score >= 70:
        return "solid"
    if score >= 55:
        return "partial"
    return "weak"


def _citation_ids(conflict: dict[str, Any]) -> list[str]:
    """Internal conflicts store line ids; serialised packets store citation objects."""
    ids = []
    for citation in conflict.get("citations", []):
        if isinstance(citation, dict):
            line_id = citation.get("line_id")
        else:
            line_id = citation
        if line_id:
            ids.append(str(line_id))
    return ids


def _missing_details(
    conflicts: list[dict[str, Any]], lines: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    ids = []
    for conflict in conflicts:
        if conflict.get("status") == "missing" and conflict.get("missing_document"):
            if conflict["missing_document"] not in ids:
                ids.append(conflict["missing_document"])
    details = []
    for document_id in ids:
        line = next(
            (item for item in lines
             if item["source_table"] == "claim_documents" and item["source_row_id"] == document_id),
            None,
        )
        payload = (line or {}).get("payload", {})
        details.append({
            "document_id": document_id,
            "name": payload.get("name") or document_id,
            "required_by": payload.get("required_by"),
            "requested_date": payload.get("requested_date"),
            "note": payload.get("note") or "",
        })
    return details


def score_appeal(
    conflicts: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    claim: dict[str, Any],
    as_of: str | date,
    policy: dict[str, Any],
) -> dict[str, Any]:
    as_of_date = _as_date(as_of) or date.today()
    stale_days = int(policy.get("stale_days", 180))
    reasons = [item for item in conflicts if item.get("kind") == "denial_reason"]
    unresolved = [item for item in reasons if item.get("status") in {"open", "unresolved"}]
    missing = [item for item in reasons if item.get("status") == "missing"]
    rebutted = [item for item in reasons if item.get("status") == "rebutted"]
    unsupported = [item for item in rebutted if len(item.get("citations", [])) < 2]

    line_map = {line["line_id"]: line for line in lines}
    stale_ids: list[str] = []
    for conflict in rebutted:
        for line_id in _citation_ids(conflict):
            line = line_map.get(line_id)
            if not line or line.get("source_table") not in {"medical_records", "eob"}:
                continue
            day = _as_date(line.get("date"))
            if day and (as_of_date - day).days > stale_days and line_id not in stale_ids:
                stale_ids.append(line_id)

    all_supported = bool(reasons) and all(
        item.get("status") == "missing"
        or (item.get("status") == "rebutted" and len(item.get("citations", [])) >= 2)
        for item in reasons
    )
    unresolved_points = int(policy.get("unresolved_penalty", 20)) * len(unresolved)
    missing_points = int(policy.get("missing_doc_penalty", 15)) * len(missing)
    unsupported_points = int(policy.get("unsupported_penalty", 10)) * len(unsupported)
    stale_points = int(policy.get("stale_penalty", 5)) * len(stale_ids)
    bonus = int(policy.get("rebuttal_bonus", 5)) if all_supported else 0
    raw = 100 - unresolved_points - missing_points - unsupported_points - stale_points + bonus
    cap = int(policy.get("missing_doc_cap", 84)) if missing else 100
    score = max(0, min(cap, raw))
    status = "conditional" if missing else (
        "ready" if not unresolved and not unsupported else "draft"
    )
    missing_details = _missing_details(reasons, lines)
    projected = min(100, raw + missing_points) if missing else score
    if missing_details:
        names = ", ".join(f"{item['name']} ({item['document_id']})" for item in missing_details)
        next_best_action = (
            f"Obtain {names}. It is required by the policy; the packet is conditional without it. "
            f"Supplying it raises the appeal strength from {score} to {projected} and makes the packet ready."
        )
    elif unresolved:
        next_best_action = "Resolve the remaining denial reason with evidence before sending."
    else:
        next_best_action = "The file is complete; send the packet and keep the evidence index attached."

    return {
        "score": score,
        "bucket": bucket_for(score),
        "status": status,
        "raw_score": raw,
        "cap": cap,
        "deductions": [
            {
                "reason": "unresolved_reason",
                "points_each": int(policy.get("unresolved_penalty", 20)),
                "count": len(unresolved),
                "points": unresolved_points,
                "items": [item.get("reason_id") for item in unresolved],
            },
            {
                "reason": "missing_required_document",
                "points_each": int(policy.get("missing_doc_penalty", 15)),
                "count": len(missing),
                "points": missing_points,
                "items": [item.get("reason_id") for item in missing],
            },
            {
                "reason": "unsupported_rebuttal",
                "points_each": int(policy.get("unsupported_penalty", 10)),
                "count": len(unsupported),
                "points": unsupported_points,
                "items": [item.get("reason_id") for item in unsupported],
            },
            {
                "reason": "stale_evidence",
                "points_each": int(policy.get("stale_penalty", 5)),
                "count": len(stale_ids),
                "points": stale_points,
                "items": stale_ids,
                "stale_days": stale_days,
            },
        ],
        "bonus": {
            "reason": "all_non_missing_reasons_rebutted_with_two_citations",
            "points": bonus,
        },
        "counts": {
            "reason_count": len(reasons),
            "rebutted": len(rebutted),
            "missing": len(missing),
            "unresolved": len(unresolved),
            "unsupported": len(unsupported),
            "stale_evidence": len(stale_ids),
        },
        "missing_documents": missing_details,
        "next_best_action": next_best_action,
        "projected_score_with_missing_fixed": projected,
        "note": (
            "This is an evidence-strength score, not a prediction of the insurer's decision. "
            "A human must review and sign the packet."
        ),
    }


def counterfactuals(
    conflicts: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    claim: dict[str, Any],
    as_of: str | date,
    policy: dict[str, Any],
) -> list[dict[str, Any]]:
    base = score_appeal(conflicts, lines, claim, as_of, policy)
    results: list[dict[str, Any]] = []
    for source in COUNTERFACTUAL_SOURCES:
        remaining_lines = [line for line in lines if line.get("source_table") != source]
        remaining_conflicts = []
        for conflict in conflicts:
            copy = dict(conflict)
            if (
                conflict.get("status") == "rebutted"
                and source in DEPENDENCIES.get(conflict.get("finding_kind"), set())
            ):
                copy["status"] = "open"
                copy["citations"] = []
                copy["counterfactual_note"] = f"depends on {source}"
            remaining_conflicts.append(copy)
        counter = score_appeal(remaining_conflicts, remaining_lines, claim, as_of, policy)
        results.append({
            "removed_source": source,
            "score_before": base["score"],
            "score_after": counter["score"],
            "score_delta": counter["score"] - base["score"],
            "bucket_after": counter["bucket"],
            "rebutted_before": base["counts"]["rebutted"],
            "rebutted_after": counter["counts"]["rebutted"],
            "rebutted_delta": counter["counts"]["rebutted"] - base["counts"]["rebutted"],
            "unresolved_after": counter["counts"]["unresolved"],
        })
    return results
