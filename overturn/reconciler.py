"""Reconciler: the only agent that calls run_sql.

It reads the planner's queries, turns the denial, policy, clinical record, EOB,
code table, document checklist and live ICD-10 descriptions into one evidence
ledger, and writes the denial reasons into the shared World Model.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from typing import Any

from .llm import LLMClient
from .prompts import reconciler_messages
from .trace import Tracer
from .world_model import WorldModel
from .zetaris import SqlClient


def _as_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _sql_str(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


class Reconciler:
    def __init__(self, sql: SqlClient, llm: LLMClient, tracer: Tracer) -> None:
        self.sql = sql
        self.llm = llm
        self.tracer = tracer
        self.last_cache: dict[str, list[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    def reconcile(self, world: WorldModel, plan: dict[str, Any], case: dict[str, Any] | None = None) -> dict[str, Any]:
        cache: dict[str, list[dict[str, Any]]] = {}
        for query in plan.get("queries", []):
            cache[query["id"]] = self.sql.run_sql(query["sql"], agent="reconciler")

        denial = self._rows(cache, "q_denial", "SELECT * FROM denial_reasons ORDER BY reason_id")
        policy = self._rows(cache, "q_policy", "SELECT * FROM policy_clauses ORDER BY section")
        records = self._rows(cache, "q_records", "SELECT * FROM medical_records ORDER BY record_date")
        eob = self._rows(cache, "q_eob", "SELECT * FROM eob")
        codes = self._rows(cache, "q_codes", "SELECT * FROM procedure_codes")
        documents = self._rows(cache, "q_docs", "SELECT * FROM claim_documents")
        icd10 = self._rows(cache, "q_icd10", "SELECT * FROM icd10_codes")
        facts = self._rows(cache, "q_facts", "SELECT * FROM claim_facts")
        evidence = self._rows(cache, "q_evidence", "SELECT * FROM appeal_evidence")
        self.last_cache = {
            "denial": denial, "policy": policy, "records": records, "eob": eob,
            "codes": codes, "documents": documents, "icd10": icd10,
            "facts": facts, "evidence": evidence,
        }

        lines = self._build_lines(policy, records, eob, codes, documents, icd10)
        for line in lines:
            world.add_line(line)
        world_lines = world.lines()
        by_source_row = {(line["source_table"], line["source_row_id"]): line["line_id"] for line in world_lines}

        claim = self._build_claim(facts, denial, records, eob, codes, icd10, documents, case)
        world.set_claim(claim)

        for reason in denial:
            conflict = self._conflict(reason, claim, world_lines, by_source_row)
            world.add_conflict(conflict)

        review = self._review_normalisation(lines, claim)
        self.tracer.event(
            "reconcile",
            agent="reconciler",
            decision=(
                f"{len(lines)} evidence lines, {len(denial)} denial reasons, "
                f"{len(claim.get('missing_documents', []))} missing document(s)"
            ),
            rows=len(lines),
            notes=review.get("notes", ""),
        )
        return {
            "line_count": len(lines),
            "reason_count": len(denial),
            "missing_documents": claim.get("missing_documents", []),
            "procedure_code": claim.get("procedure_code"),
            "diagnosis_code": claim.get("diagnosis_code"),
        }

    def _rows(
        self, cache: dict[str, list[dict[str, Any]]], query_id: str, fallback_sql: str
    ) -> list[dict[str, Any]]:
        if query_id in cache:
            return cache[query_id]
        rows = self.sql.run_sql(fallback_sql, agent="reconciler")
        cache[query_id] = rows
        return rows

    # ------------------------------------------------------------------
    def _build_lines(
        self,
        policy: list[dict[str, Any]],
        records: list[dict[str, Any]],
        eob: list[dict[str, Any]],
        codes: list[dict[str, Any]],
        documents: list[dict[str, Any]],
        icd10: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        lines: list[dict[str, Any]] = []
        for row in policy:
            lines.append({
                "source_table": "policy_clauses",
                "source_row_id": row["clause_id"],
                "date": row.get("effective_date") or "",
                "summary": f"{row['clause_id']} {row['title']}: {row['text']}",
                "category": "policy",
                "verification_status": "reference",
                "confidence": 1.0,
                "notes": f"Version {row.get('version')} effective {row.get('effective_date')}",
                "payload": {
                    "clause_id": row["clause_id"],
                    "section": row.get("section"),
                    "title": row.get("title"),
                    "text": row.get("text"),
                    "applies_to": row.get("applies_to"),
                    "version": row.get("version"),
                    "effective_date": row.get("effective_date"),
                },
            })
        for row in records:
            lines.append({
                "source_table": "medical_records",
                "source_row_id": row["record_id"],
                "date": row["record_date"],
                "summary": f"{row['record_type']} {row['record_date']}: {row['summary']}",
                "category": "clinical_record",
                "verification_status": "documented",
                "confidence": 0.90,
                "notes": row.get("notes") or "",
                "payload": {
                    "record_type": row.get("record_type"),
                    "provider": row.get("provider"),
                    "diagnosis_code": row.get("diagnosis_code"),
                    "procedure_code": row.get("procedure_code"),
                    "weeks_of_therapy": row.get("weeks_of_therapy"),
                    "summary": row.get("summary"),
                },
            })
        for row in eob:
            lines.append({
                "source_table": "eob",
                "source_row_id": row["eob_id"],
                "date": row["service_date"],
                "summary": (
                    f"Claim {row['claim_id']}: {row['procedure_code']} billed AUD {row['billed_amount']:.2f}; "
                    f"paid AUD {row['paid_amount']:.2f}; patient responsibility AUD {row['patient_responsibility']:.2f}"
                ),
                "category": "insurer_record",
                "verification_status": "documented",
                "confidence": 0.95,
                "notes": f"Denial code {row.get('denial_code')} on {row.get('denial_date')}",
                "payload": dict(row),
            })
        for row in codes:
            lines.append({
                "source_table": "procedure_codes",
                "source_row_id": row["code"],
                "date": "",
                "summary": (
                    f"{row['code']}: {row['description']}; contrast={row.get('contrast')}; "
                    f"prior_auth={bool(row.get('prior_auth_required'))}; covered={bool(row.get('covered'))}"
                ),
                "category": "procedure_code",
                "verification_status": "reference",
                "confidence": 1.0,
                "notes": row.get("notes") or "",
                "payload": dict(row),
            })
        for row in icd10:
            lines.append({
                "source_table": "icd10_codes",
                "source_row_id": row["code"],
                "date": "",
                "summary": f"{row['code']}: {row['description']}",
                "category": "diagnosis_code",
                "verification_status": "reference",
                "confidence": 0.95,
                "notes": f"Source: {row.get('source') or 'ICD-10-CM'}",
                "payload": dict(row),
            })
        for row in documents:
            missing = str(row.get("status", "")).lower() == "missing"
            lines.append({
                "source_table": "claim_documents",
                "source_row_id": row["document_id"],
                "date": row.get("document_date") or row.get("requested_date") or "",
                "summary": f"{row['name']}: {row['status']}",
                "category": "document",
                "verification_status": "missing" if missing else "present",
                "confidence": 0.0 if missing else 1.0,
                "notes": row.get("note") or "",
                "payload": dict(row),
            })
        return lines

    def _build_claim(
        self,
        facts: list[dict[str, Any]],
        denial: list[dict[str, Any]],
        records: list[dict[str, Any]],
        eob: list[dict[str, Any]],
        codes: list[dict[str, Any]],
        icd10: list[dict[str, Any]],
        documents: list[dict[str, Any]],
        case: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fact = facts[0] if facts else {}
        missing = [row for row in documents if str(row.get("status", "")).lower() == "missing"]
        procedure_code = fact.get("ordered_procedure_code") or next(
            (row.get("procedure_code") for row in reversed(records) if row.get("procedure_code")), ""
        )
        diagnosis_code = fact.get("recorded_diagnosis_code") or next(
            (row.get("diagnosis_code") for row in reversed(records) if row.get("diagnosis_code")), ""
        )
        code_row = next((row for row in codes if row.get("code") == procedure_code), {})
        diagnosis_row = next((row for row in icd10 if row.get("code") == diagnosis_code), {})
        denial_date = denial[0].get("denial_date") if denial else ""
        deadline = denial[0].get("appeal_deadline") if denial else ""
        return {
            "claim_id": (eob[0].get("claim_id") if eob else "CLM-UNKNOWN"),
            "insurer": (case or {}).get("insurer", "Northbridge Health"),
            "claimant": ((case or {}).get("claimant") or {}).get("name", "Ava"),
            "denial_date": denial_date,
            "appeal_deadline": deadline,
            "procedure_code": procedure_code,
            "procedure_description": code_row.get("description", ""),
            "diagnosis_code": diagnosis_code,
            "diagnosis_description": diagnosis_row.get("description", ""),
            "physiotherapy_sessions": int(fact.get("physiotherapy_sessions") or 0),
            "max_weeks_of_therapy": int(fact.get("max_weeks_of_therapy") or 0),
            "missing_documents": [row["document_id"] for row in missing],
            "reason_count": len(denial),
            "conditional": False,
            "diagnosis_verified": False,
            "status": "draft",
        }

    def _conflict(
        self,
        reason: dict[str, Any],
        claim: dict[str, Any],
        lines: list[dict[str, Any]],
        by_source_row: dict[tuple[str, str], str],
    ) -> dict[str, Any]:
        reason_id = reason["reason_id"]
        text = reason["reason_text"]
        cited_clause = reason.get("cited_clause")
        cited_code = reason.get("cited_code")
        cited_diagnosis = reason.get("cited_diagnosis")
        actual_code = claim.get("procedure_code")
        actual_diagnosis = claim.get("diagnosis_code")

        line_ids: list[str] = []
        for source, row_id in (
            ("policy_clauses", cited_clause),
            ("policy_clauses", "POL-4.1"),
            ("policy_clauses", "POL-4.2"),
            ("policy_clauses", "POL-5.1"),
            ("policy_clauses", "POL-6.4"),
            ("policy_clauses", "POL-7.2"),
            ("procedure_codes", cited_code),
            ("procedure_codes", actual_code),
            ("icd10_codes", cited_diagnosis),
            ("icd10_codes", actual_diagnosis),
            ("eob", "EOB-001"),
            ("claim_documents", "DOC-003"),
            ("claim_documents", "DOC-001"),
            ("claim_documents", "DOC-002"),
            ("claim_documents", "DOC-004"),
        ):
            line_id = by_source_row.get((source, row_id))
            if line_id and line_id not in line_ids:
                line_ids.append(line_id)
        for line in lines:
            if line["source_table"] == "medical_records":
                line_ids.append(line["line_id"])

        if "letter" in text.lower() or "document" in text.lower():
            action = {"type": "mark_missing", "reason_id": reason_id, "document_id": "DOC-003"}
            requery = f"SELECT * FROM claim_documents WHERE document_id = {_sql_str('DOC-003')}"
        elif cited_clause == "POL-4.3" or "experimental" in text.lower():
            action = {"type": "rebut_reason", "reason_id": reason_id}
            requery = (
                "SELECT * FROM policy_clauses WHERE clause_id IN "
                f"({_sql_str('POL-4.3')}, {_sql_str('POL-4.1')})"
            )
        elif cited_code and actual_code and cited_code != actual_code:
            action = {"type": "rebut_reason", "reason_id": reason_id}
            requery = (
                "SELECT * FROM procedure_codes WHERE code IN "
                f"({_sql_str(cited_code)}, {_sql_str(actual_code)})"
            )
        elif "conservative" in text.lower() or "necess" in text.lower():
            action = {"type": "rebut_reason", "reason_id": reason_id}
            requery = (
                "SELECT * FROM medical_records WHERE record_type IN "
                "('Physiotherapy', 'GP review', 'Physiotherapy review') ORDER BY record_date"
            )
        else:
            action = {"type": "rebut_reason", "reason_id": reason_id}
            requery = f"SELECT * FROM appeal_evidence WHERE reason_id = {_sql_str(reason_id)}"

        return {
            "kind": "denial_reason",
            "key": reason_id,
            "status": "open",
            "reason_id": reason_id,
            "reason_text": text,
            "cited_clause": cited_clause,
            "cited_code": cited_code,
            "cited_diagnosis": cited_diagnosis,
            "denial_date": reason.get("denial_date"),
            "line_ids": line_ids,
            "requery_sql": requery,
            "action": action,
            "question": f"Can the file rebut the insurer's reason: {text}",
        }

    # ------------------------------------------------------------------
    def _review_normalisation(self, lines: list[dict[str, Any]], claim: dict[str, Any]) -> dict[str, Any]:
        summary = {
            "line_count": len(lines),
            "by_source": {
                source: sum(1 for line in lines if line["source_table"] == source)
                for source in sorted({line["source_table"] for line in lines})
            },
            "missing_documents": claim.get("missing_documents", []),
            "procedure_code": claim.get("procedure_code"),
            "diagnosis_code": claim.get("diagnosis_code"),
        }

        def offline() -> dict[str, Any]:
            return {
                "accepted": True,
                "issues": [],
                "notes": "Deterministic normalisation; a missing required document stays missing.",
            }

        return self.llm.complete(
            agent="reconciler",
            kind="normalise",
            messages=reconciler_messages(summary),
            offline_fn=offline,
        )

    # ------------------------------------------------------------------
    def requery(self, world: WorldModel, instruction: dict[str, Any]) -> dict[str, Any]:
        sql = instruction.get("sql", "")
        action = instruction.get("action") or {}
        conflict_id = instruction.get("conflict_id")
        why = instruction.get("why", "critic re-query")
        if not sql:
            raise ValueError("re-query instruction missing SQL")
        try:
            rows = self.sql.run_sql(sql, agent="reconciler")
        except Exception as exc:
            self.tracer.event(
                "requery_error",
                agent="reconciler",
                decision=str(exc),
                conflict_id=conflict_id,
                sql=sql[:400],
                why=why,
            )
            return {"action": None, "why": why, "rows": 0, "error": str(exc)}
        kind = action.get("type")
        detail: dict[str, Any] = {"action": kind, "why": why, "rows": len(rows)}

        if kind == "rebut_reason":
            detail.update(self._rebut_reason(world, action))
        elif kind == "mark_missing":
            detail.update(self._mark_missing(world, action))
        elif kind == "mark_conditional":
            claim = world.claim()
            claim["conditional"] = True
            claim["status"] = "conditional"
            world.set_claim(claim)
            detail = {"action": kind, "why": why, "rows": len(rows), "summary": "packet is conditional"}
        elif kind == "verify_diagnosis":
            claim = world.claim()
            claim["diagnosis_verified"] = True
            world.set_claim(claim)
            detail = {"action": kind, "why": why, "rows": len(rows), "summary": "live ICD-10 descriptions verified"}
        elif kind == "apply_human_answer":
            detail.update(self._apply_human_answer(world, action))
        else:
            raise ValueError(f"unknown re-query action: {kind}")

        if conflict_id:
            status = "missing" if kind == "mark_missing" else "rebutted"
            world.update_conflict(
                conflict_id,
                status=status,
                resolution=detail,
                requery_rows=len(rows),
                requery_sql=sql,
                _agent="reconciler",
            )
        self.tracer.event(
            "requery_exec",
            agent="reconciler",
            decision=f"{kind}: {detail.get('summary', 'done')}",
            sql=sql,
            rows=len(rows),
            conflict_id=conflict_id,
        )
        return detail

    def _rebut_reason(self, world: WorldModel, action: dict[str, Any]) -> dict[str, Any]:
        reason_id = action.get("reason_id")
        citations = action.get("citations") or []
        rebuttal = action.get("rebuttal") or ""
        conflict = next(
            (item for item in world.conflicts() if item.get("reason_id") == reason_id), None
        )
        if not conflict:
            raise ValueError(f"no conflict for reason {reason_id}")
        citation_sources = []
        for line_id in citations:
            line = world.find_line(line_id)
            citation_sources.append(f"{line['source_table']}:{line['source_row_id']}")
        if len(citations) < 2:
            raise ValueError(f"reason {reason_id} needs at least two citations")
        world.update_conflict(
            conflict["conflict_id"],
            status="rebutted",
            rebuttal=rebuttal,
            citations=citations,
            citation_sources=citation_sources,
            confidence=min(0.99, 0.60 + 0.10 * len(citations)),
            _agent="reconciler",
        )
        return {
            "summary": f"{reason_id} rebutted with {len(citations)} citations",
            "reason_id": reason_id,
            "citations": citation_sources,
        }

    def _mark_missing(self, world: WorldModel, action: dict[str, Any]) -> dict[str, Any]:
        reason_id = action.get("reason_id")
        document_id = action.get("document_id")
        conflict = next(
            (item for item in world.conflicts() if item.get("reason_id") == reason_id), None
        )
        if not conflict:
            raise ValueError(f"no conflict for reason {reason_id}")
        document_line = next(
            (line for line in world.lines()
             if line["source_table"] == "claim_documents" and line["source_row_id"] == document_id),
            None,
        )
        if document_line:
            world.add_exclusion(
                {
                    "source_table": "claim_documents",
                    "source_row_id": document_id,
                    "summary": document_line.get("summary"),
                },
                reason="required document missing; do not fabricate",
            )
        claim = world.claim()
        missing = list(claim.get("missing_documents", []))
        if document_id and document_id not in missing:
            missing.append(document_id)
        claim["missing_documents"] = missing
        claim["conditional"] = True
        claim["status"] = "conditional"
        world.set_claim(claim)
        citations = action.get("citations", [])
        citation_sources = []
        for line_id in citations:
            try:
                line = world.find_line(line_id)
            except KeyError:
                continue
            citation_sources.append(f"{line['source_table']}:{line['source_row_id']}")
        world.update_conflict(
            conflict["conflict_id"],
            status="missing",
            missing_document=document_id,
            citations=citations,
            citation_sources=citation_sources,
            rebuttal="The document is genuinely missing; the appeal is conditional until it is supplied.",
            _agent="reconciler",
        )
        return {
            "summary": f"{reason_id} marked missing; {document_id} added to the checklist",
            "document_id": document_id,
        }

    def _apply_human_answer(self, world: WorldModel, action: dict[str, Any]) -> dict[str, Any]:
        answer = str(action.get("answer", ""))
        changed = []
        for conflict_id in action.get("conflict_ids", []):
            conflict = next(
                (item for item in world.conflicts() if item["conflict_id"] == conflict_id), None
            )
            if not conflict:
                continue
            world.update_conflict(
                conflict_id,
                status="unresolved",
                resolution={"summary": f"human answer: {answer}"},
                _agent="reconciler",
            )
            changed.append(conflict_id)
        return {"summary": f"human answer ingested; {len(changed)} reason(s) unresolved", "answer": answer}

    # ------------------------------------------------------------------
    def refresh_claim(self, world: WorldModel, case: dict[str, Any]) -> dict[str, Any]:
        claim = world.claim()
        conflicts = [item for item in world.conflicts() if item.get("kind") == "denial_reason"]
        missing = [item["reason_id"] for item in conflicts if item.get("status") == "missing"]
        open_reasons = [item["reason_id"] for item in conflicts if item.get("status") == "open"]
        rebutted = [item["reason_id"] for item in conflicts if item.get("status") == "rebutted"]
        claim["reason_count"] = len(conflicts)
        claim["missing_documents"] = list(dict.fromkeys(
            [doc for item in conflicts for doc in ([item.get("missing_document")] if item.get("missing_document") else [])]
        ))
        claim["conditional"] = bool(claim["missing_documents"])
        claim["status"] = "conditional" if claim["conditional"] else ("ready" if not open_reasons else "draft")
        claim["reasons"] = {
            "rebutted": rebutted,
            "missing": missing,
            "open": open_reasons,
        }
        claim["as_of"] = case.get("as_of")
        world.set_claim(claim)
        return claim
