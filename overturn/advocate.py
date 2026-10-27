"""Advocate: the insurer's voice. Tries to break the appeal."""

from __future__ import annotations

from typing import Any

from .critic import compute_stats
from .llm import LLMClient
from .prompts import advocate_messages
from .trace import Tracer
from .world_model import WorldModel


class Advocate:
    def __init__(self, llm: LLMClient, tracer: Tracer) -> None:
        self.llm = llm
        self.tracer = tracer

    def review(self, world: WorldModel, claim: dict[str, Any], iteration: int) -> dict[str, Any]:
        stats = compute_stats(world)
        messages = advocate_messages(claim, stats)

        def fallback_requery() -> dict[str, Any]:
            return {
                "sql": "SELECT * FROM claim_documents WHERE document_id = 'DOC-003'",
                "action": {"type": "mark_conditional"},
                "why": "The insurer can reject an incomplete appeal; state the missing specialist letter.",
            }

        def offline() -> dict[str, Any]:
            missing = bool(stats["missing_documents"]) and not stats["conditional"]
            diagnosis_unverified = not stats["diagnosis_verified"]
            attacks = [
                {
                    "claim": "The experimental exclusion applies to the service.",
                    "evidence": {"reason": "DEN-01", "clause": "POL-4.3"},
                    "severity": "medium",
                },
                {
                    "claim": "The service was billed with contrast and required prior authorisation.",
                    "evidence": {"reason": "DEN-02", "cited_code": "MRI-LS-002", "record_code": stats["procedure_code"]},
                    "severity": "medium",
                },
                {
                    "claim": "The record does not prove six weeks of conservative treatment.",
                    "evidence": {"reason": "DEN-03", "weeks": claim.get("max_weeks_of_therapy")},
                    "severity": "medium",
                },
                {
                    "claim": "The specialist referral letter is missing; the appeal is incomplete.",
                    "evidence": {"reason": "DEN-04", "missing_documents": stats["missing_documents"]},
                    "severity": "high" if missing else "low",
                },
            ]
            if diagnosis_unverified:
                attacks.insert(1, {
                    "claim": "The denial cites diagnosis M51.1; the file must show the live ICD-10 description before the code argument stands.",
                    "evidence": {"cited": "M51.1", "record": stats["diagnosis_code"]},
                    "severity": "high",
                })
            if diagnosis_unverified:
                requery = {
                    "sql": "SELECT * FROM icd10_codes WHERE code IN ('M51.1', 'M54.5')",
                    "action": {"type": "verify_diagnosis"},
                    "why": "The insurer's diagnosis code and the record's diagnosis code differ.",
                }
            elif missing:
                requery = fallback_requery()
            else:
                requery = None
            return {
                "attacks": attacks,
                "breaks_claim": missing or diagnosis_unverified,
                "requery": requery,
                "rebuttals_needed": [
                    "Quote the clause that actually applies.",
                    "Show the code and diagnosis in the file.",
                    "Show the dated conservative treatment.",
                    "State the missing letter; do not invent it.",
                ],
            }

        result = self.llm.complete(
            agent="advocate",
            kind="adversarial_review",
            messages=messages,
            offline_fn=offline,
            iteration=iteration,
        )
        if result.get("breaks_claim") and not result.get("requery"):
            result["requery"] = fallback_requery()
        if result.get("breaks_claim") and not result.get("requery"):
            result["breaks_claim"] = False
            result.setdefault("notes", "Claim challenged; no further evidence could settle it.")

        self.tracer.event(
            "advocate_review",
            agent="advocate",
            mode="adversarial_review",
            decision=(
                f"{'breaks' if result.get('breaks_claim') else 'appeal survives'}; "
                f"{len(result.get('attacks', []))} attack(s)"
            ),
            iteration=iteration,
            notes=result.get("notes", ""),
        )
        return result
