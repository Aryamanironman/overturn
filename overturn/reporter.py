"""Reporter: assembles the appeal packet, hash chain and rebuttal annex.

Every figure and quote comes from the computed ledger and the policy text. The
Reporter model writes prose only from supplied facts; unsupported numbers or
quotes are rejected. A missing document is always stated as missing.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .llm import LLMClient
from .prompts import reporter_messages
from .trace import Tracer, canonical_json
from .world_model import WorldModel

GENESIS = "0" * 64
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
QUOTE_RE = re.compile(r"[“\"]([^”\"]{12,})[”\"]")


def hash_chain(lines: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    chained: list[dict[str, Any]] = []
    previous = GENESIS
    for line in sorted(lines, key=lambda item: item["line_id"]):
        payload = {key: value for key, value in line.items() if key not in {"hash", "prev_hash"}}
        digest = hashlib.sha256((previous + "|" + canonical_json(payload)).encode("utf-8")).hexdigest()
        record = dict(line)
        record["prev_hash"] = previous
        record["hash"] = digest
        chained.append(record)
        previous = digest
    return chained, previous


def verify_chain(chained: list[dict[str, Any]], head: str) -> bool:
    previous = GENESIS
    for line in sorted(chained, key=lambda item: item["line_id"]):
        payload = {key: value for key, value in line.items() if key not in {"hash", "prev_hash"}}
        digest = hashlib.sha256((previous + "|" + canonical_json(payload)).encode("utf-8")).hexdigest()
        if line.get("prev_hash") != previous or line.get("hash") != digest:
            return False
        previous = digest
    return previous == head


def _reason_payload(conflict: dict[str, Any], line_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    citations = []
    for line_id in conflict.get("citations", []):
        line = line_map.get(line_id)
        if line:
            citations.append({
                "line_id": line_id,
                "source": f"{line['source_table']}:{line['source_row_id']}",
                "summary": line.get("summary", ""),
            })
    return {
        "kind": "denial_reason",
        "reason_id": conflict.get("reason_id"),
        "reason_text": conflict.get("reason_text"),
        "status": conflict.get("status"),
        "cited_clause": conflict.get("cited_clause"),
        "cited_code": conflict.get("cited_code"),
        "cited_diagnosis": conflict.get("cited_diagnosis"),
        "finding_kind": conflict.get("finding_kind"),
        "rebuttal": conflict.get("rebuttal") or conflict.get("finding_note") or "",
        "citations": citations,
        "missing_document": conflict.get("missing_document"),
        "confidence": conflict.get("confidence"),
    }


def _facts(
    case: dict[str, Any],
    claim: dict[str, Any],
    world: WorldModel,
    score: dict[str, Any],
    counterfactuals: list[dict[str, Any]],
) -> dict[str, Any]:
    lines = world.lines()
    line_map = {line["line_id"]: line for line in lines}
    reasons = [
        _reason_payload(item, line_map)
        for item in world.conflicts()
        if item.get("kind") == "denial_reason"
    ]
    policy_quotes = {
        line["source_row_id"]: line.get("payload", {}).get("text")
        for line in lines
        if line["source_table"] == "policy_clauses"
    }
    evidence = [
        {
            "line_id": line["line_id"],
            "source": f"{line['source_table']}:{line['source_row_id']}",
            "date": line.get("date"),
            "summary": line.get("summary"),
            "status": line.get("verification_status"),
            "confidence": line.get("confidence"),
        }
        for line in lines
        if line["source_table"] != "claim_documents" or line.get("verification_status") != "present"
    ]
    return {
        "case": case,
        "claim": claim,
        "reasons": reasons,
        "missing_documents": score.get("missing_documents", []),
        "score": {
            "score": score.get("score"),
            "bucket": score.get("bucket"),
            "status": score.get("status"),
            "raw_score": score.get("raw_score"),
            "cap": score.get("cap"),
            "next_best_action": score.get("next_best_action"),
        },
        "counterfactuals": counterfactuals,
        "policy_quotes": policy_quotes,
        "evidence": evidence,
    }


def _offline_annex(facts: dict[str, Any]) -> dict[str, Any]:
    case = facts["case"]
    claim = facts["claim"]
    reasons = facts["reasons"]
    rebutted = [item for item in reasons if item["status"] == "rebutted"]
    missing = [item for item in reasons if item["status"] == "missing"]
    missing_names = ", ".join(
        f"{item['name']} ({item['document_id']})" for item in facts["missing_documents"]
    ) or "none"
    cover_letter = (
        f"I am requesting an internal appeal of {case.get('insurer')}'s denial dated "
        f"{claim.get('denial_date')} for claim {claim.get('claim_id')}. "
        f"The denial gives {len(reasons)} reasons; {len(rebutted)} are contradicted by the policy, "
        f"the clinical record or the coding. "
        + (
            f"The remaining reason concerns a missing required document: {missing_names}. "
            "It is listed in the checklist and will be supplied; it has not been fabricated. "
            if missing else ""
        )
        + "The evidence for each reason is indexed below."
    )
    rebuttals = []
    for reason in reasons:
        if reason["status"] == "rebutted":
            text = reason["rebuttal"]
        elif reason["status"] == "missing":
            text = (
                "This required document is genuinely missing from the file. It is listed in the "
                "checklist and will be supplied. It has not been fabricated."
            )
        else:
            text = "This reason remains unresolved; no rebuttal is asserted."
        rebuttals.append({"reason_id": reason["reason_id"], "text": text})
    return {
        "cover_letter": cover_letter,
        "rebuttals": rebuttals,
        "limitations": [
            "This packet assembles evidence for human review. It is not medical or legal advice.",
            "It does not predict the insurer's decision; a human must review and sign it.",
            "No missing document has been fabricated.",
        ],
    }


def _numbers_supported(annex: dict[str, Any], facts: dict[str, Any]) -> bool:
    allowed = set(NUMBER_RE.findall(canonical_json(facts)))
    text = canonical_json(annex)
    for number in NUMBER_RE.findall(text):
        cleaned = number.replace(",", "")
        if number in allowed or cleaned in allowed:
            continue
        try:
            value = float(cleaned)
        except ValueError:
            return False
        candidates = [float(item.replace(",", "")) for item in allowed if NUMBER_RE.fullmatch(item)]
        if not any(abs(value - candidate) < 0.051 for candidate in candidates):
            return False
    return True


def _quotes_supported(annex: dict[str, Any], facts: dict[str, Any]) -> bool:
    haystack = canonical_json(facts).lower()
    for quote in QUOTE_RE.findall(canonical_json(annex)):
        normalized = re.sub(r"\s+", " ", quote).strip().lower()
        if normalized and normalized not in re.sub(r"\s+", " ", haystack):
            return False
    return True


class Reporter:
    def __init__(self, llm: LLMClient, tracer: Tracer) -> None:
        self.llm = llm
        self.tracer = tracer

    def write(
        self,
        *,
        case: dict[str, Any],
        policy: dict[str, Any],
        plan: dict[str, Any],
        claim: dict[str, Any],
        world: WorldModel,
        score: dict[str, Any],
        counterfactuals: list[dict[str, Any]],
        reviews: dict[str, Any],
        routing: dict[str, str],
    ) -> dict[str, Any]:
        facts = _facts(case, claim, world, score, counterfactuals)
        offline = _offline_annex(facts)
        annex = self.llm.complete(
            agent="reporter",
            kind="appeal_annex",
            messages=reporter_messages(facts),
            offline_fn=lambda: offline,
        )
        if (
            not isinstance(annex.get("cover_letter"), str)
            or not isinstance(annex.get("rebuttals"), list)
            or not _numbers_supported(annex, facts)
            or not _quotes_supported(annex, facts)
        ):
            annex = offline
            self.tracer.event(
                "reporter_validation",
                agent="reporter",
                decision="rejected model prose with unsupported numbers or quotes; used computed annex",
            )
        else:
            self.tracer.event(
                "reporter_validation",
                agent="reporter",
                decision="model prose passed numeric and quote provenance checks",
            )

        chained, head = hash_chain(world.lines())
        packet = {
            "document": "OVERTURN Appeal Packet",
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "case": case,
            "claim": claim,
            "policy_summary": {
                "purpose": policy.get("purpose"),
                "headline": policy.get("headline"),
                "classification_reason": policy.get("classification_reason"),
            },
            "plan": plan,
            "appeal_strength": score,
            "denial_reasons": facts["reasons"],
            "evidence": chained,
            "missing_documents": score.get("missing_documents", []),
            "counterfactuals": counterfactuals,
            "cover_letter": annex.get("cover_letter", ""),
            "rebuttals": annex.get("rebuttals", []),
            "limitations": annex.get("limitations", []),
            "agent_reviews": {
                "critic": reviews.get("critic", {}),
                "advocate": reviews.get("advocate", {}),
            },
            "model_routing": routing,
            "provenance": {
                "algorithm": "sha256-chain-v1",
                "genesis": GENESIS,
                "head_hash": head,
                "line_count": len(chained),
                "canonicalisation": "json sorted keys, compact separators, UTF-8",
            },
        }
        self.tracer.event(
            "report",
            agent="reporter",
            decision=f"packet built, {len(chained)} evidence lines, head {head[:12]}",
        )
        return packet


def write_packet_json(packet: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_packet_md(packet: dict[str, Any], path: Path) -> None:
    claim = packet["claim"]
    strength = packet["appeal_strength"]
    reasons = packet["denial_reasons"]
    case = packet["case"]
    rebuttals = {item["reason_id"]: item["text"] for item in packet.get("rebuttals", [])}
    parts: list[str] = []
    parts.append("# OVERTURN — Internal Appeal Packet\n")
    parts.append(
        f"**Claimant:** {case.get('claimant', {}).get('name', '')}  \n"
        f"**Insurer:** {case.get('insurer', '')}  \n"
        f"**Claim:** {claim.get('claim_id', '')}  \n"
        f"**Denial date:** {claim.get('denial_date', '')}  \n"
        f"**Appeal deadline:** {claim.get('appeal_deadline', '')}  \n"
        f"**Procedure:** {claim.get('procedure_code', '')} — {claim.get('procedure_description', '')}  \n"
        f"**Diagnosis:** {claim.get('diagnosis_code', '')} — {claim.get('diagnosis_description', '')}\n"
    )
    parts.append("\n## Appeal strength\n")
    parts.append(
        f"**{strength.get('score')} / 100 — {strength.get('bucket')} — {strength.get('status')}.**  \n"
        f"Raw {strength.get('raw_score')}, capped at {strength.get('cap')} because a required document is missing.  \n"
        f"{strength.get('note', '')}\n"
    )
    if packet.get("missing_documents"):
        parts.append("\n### Send this first\n")
        for item in packet["missing_documents"]:
            parts.append(
                f"- **{item.get('name')}** ({item.get('document_id')}) — required by "
                f"{item.get('required_by')}. {item.get('note', '')}\n"
            )
    parts.append("\n## Why the denial is wrong\n")
    parts.append("| Reason | Status | Rebuttal | Sources |\n|---|---|---|---|\n")
    for reason in reasons:
        sources = ", ".join(item["source"] for item in reason.get("citations", [])) or "—"
        parts.append(
            f"| {reason.get('reason_id')} — {reason.get('reason_text')} | "
            f"{reason.get('status')} | {rebuttals.get(reason.get('reason_id'), reason.get('rebuttal', ''))} | "
            f"{sources} |\n"
        )
    parts.append("\n## Cover letter\n")
    parts.append(packet.get("cover_letter", "") + "\n")
    parts.append("\n## Evidence index\n")
    parts.append("| Line | Source | Date | Summary | Status | Hash |\n|---|---|---|---|---|---|\n")
    for line in packet["evidence"]:
        parts.append(
            f"| {line['line_id']} | {line['source_table']}:{line['source_row_id']} | "
            f"{line.get('date', '')} | {line.get('summary', '')} | "
            f"{line.get('verification_status', '')} | `{line['hash'][:12]}…` |\n"
        )
    parts.append("\n## Counterfactuals\n")
    parts.append("| Removed source | Strength | Change | Reasons rebutted |\n|---|---:|---:|---:|\n")
    for item in packet["counterfactuals"]:
        parts.append(
            f"| {item['removed_source']} | {item['score_before']} → {item['score_after']} | "
            f"{item['score_delta']:+d} | {item['rebutted_before']} → {item['rebutted_after']} |\n"
        )
    parts.append("\n## Limitations\n")
    for limitation in packet.get("limitations", []):
        parts.append(f"- {limitation}\n")
    parts.append("\n## Provenance\n")
    parts.append(
        f"SHA-256 chain over {packet['provenance']['line_count']} evidence lines. Head "
        f"`{packet['provenance']['head_hash']}`. Any edit to an evidence line breaks the chain.\n"
    )
    path.write_text("".join(parts), encoding="utf-8")
