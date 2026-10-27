"""Planner: decomposes the appeal request and selects sources."""

from __future__ import annotations

from typing import Any

from .llm import LLMClient
from .prompts import planner_messages
from .trace import Tracer

ALLOWED_SOURCES = {
    "policy_clauses",
    "denial_reasons",
    "medical_records",
    "eob",
    "procedure_codes",
    "claim_documents",
    "icd10_codes",
    "appeal_evidence",
    "claim_facts",
}

DEFAULT_QUERIES = [
    {"id": "q_denial", "sql": "SELECT * FROM denial_reasons ORDER BY reason_id", "why": "the insurer's stated reasons"},
    {"id": "q_policy", "sql": "SELECT * FROM policy_clauses ORDER BY section", "why": "the contract the denial cites"},
    {"id": "q_records", "sql": "SELECT * FROM medical_records ORDER BY record_date", "why": "dated clinical evidence"},
    {"id": "q_eob", "sql": "SELECT * FROM eob", "why": "the insurer's own claim record"},
    {"id": "q_codes", "sql": "SELECT * FROM procedure_codes", "why": "what the codes actually mean"},
    {"id": "q_docs", "sql": "SELECT * FROM claim_documents", "why": "what is present and what is missing"},
    {"id": "q_icd10", "sql": "SELECT * FROM icd10_codes", "why": "the live/public diagnosis descriptions"},
    {"id": "q_facts", "sql": "SELECT * FROM claim_facts", "why": "the claim's deterministic facts"},
    {"id": "q_evidence", "sql": "SELECT * FROM appeal_evidence", "why": "the joined denial-policy-code view"},
]


def default_plan(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "sources": list(policy.get("required_sources", [])) + ["appeal_evidence", "claim_facts"],
        "steps": [
            "Read the insurer's denial reasons and the clauses they cite.",
            "Read the clinical record and the EOB.",
            "Resolve the procedure and diagnosis codes against the code tables.",
            "Check the claim document checklist, including anything missing.",
            "Build a reason-by-reason evidence ledger; never fill a missing document.",
        ],
        "queries": [dict(query) for query in DEFAULT_QUERIES],
        "claim_to_test": (
            "The denial reasons are not supported by the policy, the clinical record or the coding; "
            "the missing specialist letter makes the appeal conditional."
        ),
        "assumptions": [
            "The policy version effective on the denial date is the controlling version.",
            "A missing required document stays missing until a human supplies it.",
        ],
    }


class Planner:
    def __init__(self, llm: LLMClient, tracer: Tracer) -> None:
        self.llm = llm
        self.tracer = tracer

    def run(
        self,
        case: dict[str, Any],
        policy: dict[str, Any],
        memory: list[dict[str, Any]],
    ) -> dict[str, Any]:
        messages = planner_messages(case, policy, memory)
        result = self.llm.complete(
            agent="planner",
            kind="decompose",
            messages=messages,
            offline_fn=lambda: default_plan(policy),
        )
        plan = self._normalise(result, policy)
        self.tracer.event(
            "plan",
            agent="planner",
            decision=f"{len(plan['queries'])} queries over {len(plan['sources'])} sources",
            sources=plan["sources"],
            queries=[query["id"] for query in plan["queries"]],
        )
        return plan

    def _normalise(self, result: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
        plan = default_plan(policy)
        sources = [source for source in result.get("sources", []) if source in ALLOWED_SOURCES]
        if sources:
            plan["sources"] = sources
        queries = result.get("queries")
        if isinstance(queries, list):
            cleaned = []
            for index, query in enumerate(queries):
                if not isinstance(query, dict):
                    continue
                sql = str(query.get("sql", "")).strip()
                if not sql:
                    continue
                cleaned.append({
                    "id": str(query.get("id") or f"q_custom_{index}"),
                    "sql": sql,
                    "why": str(query.get("why", "planner-selected")),
                })
            if cleaned:
                existing = {query["id"] for query in cleaned}
                for required in DEFAULT_QUERIES:
                    if required["id"] not in existing:
                        cleaned.append(dict(required))
                plan["queries"] = cleaned
        if isinstance(result.get("claim_to_test"), str) and result["claim_to_test"].strip():
            plan["claim_to_test"] = result["claim_to_test"].strip()
        if isinstance(result.get("steps"), list):
            plan["steps"] = [str(step) for step in result["steps"]]
        if isinstance(result.get("assumptions"), list):
            plan["assumptions"] = [str(item) for item in result["assumptions"]]
        return plan
