"""Deterministic request router. Classifies the request and sets policy."""

from __future__ import annotations

import re
from typing import Any

POLICIES: dict[str, dict[str, Any]] = {
    "denial_appeal": {
        "purpose": "denial_appeal",
        "lookback_days": 365,
        "appeal_window_days": 60,
        "stale_days": 180,
        "missing_doc_penalty": 15,
        "unresolved_penalty": 20,
        "unsupported_penalty": 10,
        "stale_penalty": 5,
        "rebuttal_bonus": 5,
        "missing_doc_cap": 84,
        "required_sources": [
            "policy_clauses",
            "denial_reasons",
            "medical_records",
            "eob",
            "procedure_codes",
            "claim_documents",
            "icd10_codes",
        ],
        "headline": "an evidence-backed internal appeal",
    },
    "billing_error": {
        "purpose": "billing_error",
        "lookback_days": 365,
        "appeal_window_days": 90,
        "stale_days": 180,
        "missing_doc_penalty": 15,
        "unresolved_penalty": 20,
        "unsupported_penalty": 10,
        "stale_penalty": 5,
        "rebuttal_bonus": 5,
        "missing_doc_cap": 84,
        "required_sources": [
            "policy_clauses",
            "medical_records",
            "eob",
            "procedure_codes",
            "claim_documents",
        ],
        "headline": "a billing-error dispute",
    },
    "prior_auth": {
        "purpose": "prior_auth",
        "lookback_days": 365,
        "appeal_window_days": 30,
        "stale_days": 180,
        "missing_doc_penalty": 15,
        "unresolved_penalty": 20,
        "unsupported_penalty": 10,
        "stale_penalty": 5,
        "rebuttal_bonus": 5,
        "missing_doc_cap": 84,
        "required_sources": [
            "policy_clauses",
            "medical_records",
            "procedure_codes",
            "claim_documents",
        ],
        "headline": "a prior-authorisation request",
    },
}

KEYWORDS = {
    "denial_appeal": [
        "denied", "denial", "deny", "appeal", "refused", "not covered",
        "not medically necessary", "experimental", "internal review",
    ],
    "billing_error": [
        "overcharge", "overcharged", "duplicate charge", "billing error",
        "wrong charge", "invoice", "bill error", "refund",
    ],
    "prior_auth": [
        "prior authorization", "prior authorisation", "pre-authorization",
        "pre-authorisation", "pre-approval", "pre approval",
    ],
}


def route_request(request_text: str, hint: str | None = None) -> dict[str, Any]:
    text = (request_text or "").lower()
    matched: dict[str, list[str]] = {}
    for purpose, words in KEYWORDS.items():
        hits = [word for word in words if re.search(rf"\b{re.escape(word)}\b", text)]
        if hits:
            matched[purpose] = hits

    if hint in POLICIES:
        purpose = hint
        reason = f"case hint '{hint}'"
    elif matched:
        purpose = max(matched, key=lambda key: len(matched[key]))
        reason = f"keywords {matched[purpose]}"
    else:
        purpose = "denial_appeal"
        reason = "default policy for an unspecified claim problem"

    policy = dict(POLICIES[purpose])
    policy["matched_terms"] = matched.get(purpose, [])
    policy["classification_reason"] = reason
    return policy
