"""Critic: evidence detectors and adversarial review for a denied claim.

conflict_check runs deterministic evidence detectors, then asks the model to
review them. A confirmed finding always keeps its re-query and action: the
model cannot dismiss a contradiction the evidence supports.
"""

from __future__ import annotations

from typing import Any

from .llm import LLMClient
from .prompts import critic_adversarial_messages, critic_conflict_messages
from .trace import Tracer
from .world_model import WorldModel


def _find(lines: list[dict[str, Any]], source_table: str, row_id: str) -> dict[str, Any] | None:
    return next(
        (line for line in lines
         if line["source_table"] == source_table and line["source_row_id"] == row_id),
        None,
    )


def compute_stats(world: WorldModel) -> dict[str, Any]:
    conflicts = [item for item in world.conflicts() if item.get("kind") == "denial_reason"]
    rebutted = [item for item in conflicts if item.get("status") == "rebutted"]
    missing = [item for item in conflicts if item.get("status") == "missing"]
    open_reasons = [item for item in conflicts if item.get("status") == "open"]
    claim = world.claim()
    return {
        "reason_count": len(conflicts),
        "rebutted": [item.get("reason_id") for item in rebutted],
        "missing": [item.get("reason_id") for item in missing],
        "open": [item.get("reason_id") for item in open_reasons],
        "missing_documents": claim.get("missing_documents", []),
        "conditional": bool(claim.get("conditional")),
        "citations": sum(len(item.get("citations", [])) for item in conflicts),
        "procedure_code": claim.get("procedure_code"),
        "diagnosis_code": claim.get("diagnosis_code"),
        "diagnosis_verified": bool(claim.get("diagnosis_verified")),
    }


class Critic:
    def __init__(self, llm: LLMClient, tracer: Tracer) -> None:
        self.llm = llm
        self.tracer = tracer

    # ------------------------------------------------------------------
    def conflict_check(self, world: WorldModel, iteration: int) -> dict[str, Any]:
        lines = world.lines()
        claim = world.claim()
        open_conflicts = [
            item for item in world.conflicts()
            if item.get("kind") == "denial_reason" and item.get("status") == "open"
        ]
        findings: list[dict[str, Any]] = []
        for conflict in open_conflicts:
            finding = self._analyse(conflict, lines, claim)
            if finding:
                findings.append(finding)

        messages = critic_conflict_messages(findings, compute_stats(world))

        def offline() -> dict[str, Any]:
            return {
                "confirmed_indices": list(range(len(findings))),
                "dismissed_indices": [],
                "notes": (
                    f"{len(findings)} evidence-backed finding(s); missing documents stay missing."
                    if findings else "No evidence-backed conflict found in this pass."
                ),
            }

        review = self.llm.complete(
            agent="critic",
            kind="conflict_check",
            messages=messages,
            offline_fn=offline,
            iteration=iteration,
        )
        model_confirmed = [
            index for index in review.get("confirmed_indices", [])
            if isinstance(index, int) and 0 <= index < len(findings)
        ]
        dismissed = [index for index in review.get("dismissed_indices", []) if isinstance(index, int)]
        confirmed = sorted(set(model_confirmed) | set(range(len(findings))))

        applied = []
        for index in confirmed:
            finding = findings[index]
            world.update_conflict(
                finding["conflict_id"],
                requery_sql=finding["requery_sql"],
                action=finding["action"],
                finding_kind=finding["kind"],
                finding_note=finding.get("rebuttal", ""),
                _agent="critic",
            )
            applied.append(finding)

        self.tracer.event(
            "critic_findings",
            agent="critic",
            mode="conflict_check",
            decision=(
                f"{len(applied)} finding(s) over {len(open_conflicts)} open reason(s)"
                + (f"; {len(dismissed)} model dismissal(s) overruled by evidence" if dismissed else "")
            ),
            iteration=iteration,
            findings=[item["kind"] for item in applied],
            notes=review.get("notes", ""),
        )
        return {
            "findings": applied,
            "notes": review.get("notes", ""),
            "dismissed_by_model": dismissed,
        }

    # ------------------------------------------------------------------
    def _analyse(
        self, conflict: dict[str, Any], lines: list[dict[str, Any]], claim: dict[str, Any]
    ) -> dict[str, Any] | None:
        reason_id = conflict.get("reason_id")
        text = str(conflict.get("reason_text", "")).lower()
        cited_clause = conflict.get("cited_clause")
        cited_code = conflict.get("cited_code")
        cited_diagnosis = conflict.get("cited_diagnosis")
        actual_code = claim.get("procedure_code")
        actual_diagnosis = claim.get("diagnosis_code")
        weeks = int(claim.get("max_weeks_of_therapy") or 0)
        sessions = int(claim.get("physiotherapy_sessions") or 0)

        policy_cite = _find(lines, "policy_clauses", cited_clause) if cited_clause else None
        policy_4_1 = _find(lines, "policy_clauses", "POL-4.1")
        policy_4_2 = _find(lines, "policy_clauses", "POL-4.2")
        policy_4_3 = _find(lines, "policy_clauses", "POL-4.3")
        policy_5_1 = _find(lines, "policy_clauses", "POL-5.1")
        policy_6_4 = _find(lines, "policy_clauses", "POL-6.4")
        policy_7_2 = _find(lines, "policy_clauses", "POL-7.2")
        code_cite = _find(lines, "procedure_codes", cited_code) if cited_code else None
        code_actual = _find(lines, "procedure_codes", actual_code) if actual_code else None
        icd_cite = _find(lines, "icd10_codes", cited_diagnosis) if cited_diagnosis else None
        icd_actual = _find(lines, "icd10_codes", actual_diagnosis) if actual_diagnosis else None
        eob = _find(lines, "eob", "EOB-001")
        order = next(
            (line for line in lines
             if line["source_table"] == "medical_records"
             and line.get("payload", {}).get("procedure_code") == actual_code),
            None,
        )
        physio = [
            line for line in lines
            if line["source_table"] == "medical_records"
            and line.get("payload", {}).get("record_type") == "Physiotherapy"
        ]
        gp_review = next(
            (line for line in lines
             if line["source_table"] == "medical_records"
             and line.get("payload", {}).get("record_type") == "GP review"),
            None,
        )
        document = next(
            (line for line in lines
             if line["source_table"] == "claim_documents"
             and line.get("payload", {}).get("status") == "missing"),
            None,
        )

        def action(kind: str, citations: list[dict[str, Any] | None], rebuttal: str) -> dict[str, Any]:
            ids = [line["line_id"] for line in citations if line]
            return {
                "conflict_id": conflict["conflict_id"],
                "kind": kind,
                "reason_id": reason_id,
                "citations": ids,
                "rebuttal": rebuttal,
                "action": {
                    "type": "rebut_reason",
                    "reason_id": reason_id,
                    "citations": ids,
                    "rebuttal": rebuttal,
                },
            }

        # 1. The cited experimental clause does not apply to diagnostic MRI.
        if policy_cite and (
            "experimental" in str(policy_cite.get("payload", {}).get("title", "")).lower()
            or conflict.get("cited_clause") == "POL-4.3"
        ):
            applies_to = str(policy_cite.get("payload", {}).get("applies_to", ""))
            if actual_code and actual_code not in applies_to:
                citations = [policy_cite, policy_4_1, order, eob]
                rebuttal = (
                    f"The denial cites {cited_clause}, the experimental exclusion. That clause applies to "
                    f"{applies_to} and states it does not apply to diagnostic MRI of the lumbar spine. "
                    f"{policy_4_1.get('source_row_id') if policy_4_1 else 'POL-4.1'} covers "
                    f"{actual_code} after at least six weeks of conservative therapy."
                )
                finding = action("wrong_clause", citations, rebuttal)
                finding["requery_sql"] = (
                    "SELECT * FROM policy_clauses WHERE clause_id IN "
                    f"('{cited_clause}', 'POL-4.1')"
                )
                return finding

        # 2. The code and diagnosis in the denial differ from the file.
        if cited_code and actual_code and cited_code != actual_code:
            citations = [code_cite, code_actual, eob, order, icd_cite, icd_actual]
            rebuttal = (
                f"The denial cites {cited_code} and diagnosis {cited_diagnosis}. The order, the EOB and "
                f"the record use {actual_code} and diagnosis {actual_diagnosis}. "
                f"{actual_code} is described as '{code_actual.get('payload', {}).get('description', '') if code_actual else ''}' "
                f"and does not require prior authorisation; {cited_code} is the contrast study that does."
            )
            finding = action("code_mismatch", citations, rebuttal)
            finding["requery_sql"] = (
                "SELECT * FROM procedure_codes WHERE code IN "
                f"('{cited_code}', '{actual_code}')"
            )
            return finding

        # 3. The record documents conservative treatment.
        if ("conservative" in text or "necess" in text) and weeks >= 6:
            citations = [policy_5_1, order, gp_review] + physio
            rebuttal = (
                f"The record documents {sessions} physiotherapy sessions over {weeks} weeks and an NSAID "
                f"trial. {policy_5_1.get('source_row_id') if policy_5_1 else 'POL-5.1'} requires at least "
                "six weeks of conservative therapy."
            )
            finding = action("medical_necessity", citations, rebuttal)
            finding["requery_sql"] = (
                "SELECT * FROM medical_records WHERE record_type IN "
                "('Physiotherapy', 'GP review', 'Physiotherapy review') ORDER BY record_date"
            )
            return finding

        # 4. The required document is genuinely missing.
        if ("letter" in text or "document" in text) and document:
            citation_ids = [line["line_id"] for line in (policy_6_4, document) if line]
            return {
                "conflict_id": conflict["conflict_id"],
                "kind": "missing_document",
                "reason_id": reason_id,
                "citations": citation_ids,
                "rebuttal": (
                    "The specialist referral letter is genuinely missing from the file. The appeal is "
                    "conditional until it is supplied; it must not be fabricated."
                ),
                "requery_sql": "SELECT * FROM claim_documents WHERE document_id = 'DOC-003'",
                "action": {
                    "type": "mark_missing",
                    "reason_id": reason_id,
                    "document_id": document.get("source_row_id", "DOC-003"),
                    "citations": citation_ids,
                },
            }
        return None

    # ------------------------------------------------------------------
    def adversarial_review(
        self, world: WorldModel, claim: dict[str, Any], iteration: int
    ) -> dict[str, Any]:
        stats = compute_stats(world)
        messages = critic_adversarial_messages(claim, stats)

        def offline() -> dict[str, Any]:
            missing = bool(stats["missing_documents"]) and not stats["conditional"]
            diagnosis_unverified = not stats["diagnosis_verified"]
            attacks = []
            if missing:
                attacks.append({
                    "claim": "The specialist referral letter is missing; the appeal is incomplete.",
                    "evidence": stats["missing_documents"],
                    "severity": "high",
                })
            if diagnosis_unverified:
                attacks.append({
                    "claim": "The denial cites diagnosis M51.1 while the record uses M54.5; verify the live ICD-10 descriptions before relying on the code mismatch.",
                    "evidence": {"cited": "M51.1", "record": stats["diagnosis_code"]},
                    "severity": "high",
                })
            attacks.append({
                "claim": "The policy version effective on the denial date must control the analysis.",
                "evidence": {"policy_version": "2026.1", "denial_date": claim.get("denial_date")},
                "severity": "low",
            })
            if diagnosis_unverified:
                requery = {
                    "sql": "SELECT * FROM icd10_codes WHERE code IN ('M51.1', 'M54.5')",
                    "action": {"type": "verify_diagnosis"},
                    "why": "The denial and the record use different diagnosis codes; verify the live descriptions.",
                }
            elif missing:
                requery = {
                    "sql": "SELECT * FROM claim_documents WHERE document_id = 'DOC-003'",
                    "action": {"type": "mark_conditional"},
                    "why": "The packet must state that the specialist letter is missing.",
                }
            else:
                requery = None
            return {
                "attacks": attacks,
                "breaks_claim": missing or diagnosis_unverified,
                "requery": requery,
                "notes": "The appeal survives once the missing document is stated and the live ICD-10 descriptions are verified.",
            }

        result = self.llm.complete(
            agent="critic",
            kind="adversarial_review",
            messages=messages,
            offline_fn=offline,
            iteration=iteration,
        )
        self.tracer.event(
            "adversarial_review",
            agent="critic",
            mode="adversarial_review",
            decision=(
                f"{'breaks' if result.get('breaks_claim') else 'survives'} the appeal; "
                f"{len(result.get('attacks', []))} attack(s)"
            ),
            iteration=iteration,
            notes=result.get("notes", ""),
        )
        return result
