"""All agent prompts in one place. Each agent must answer with a JSON object."""

from __future__ import annotations

import json
from typing import Any


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str)


def planner_messages(case: dict[str, Any], policy: dict[str, Any], memory: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are the Planner in OVERTURN, an insurance-denial appeal system. "
                "Decompose the request and select the sources to query. You do not run SQL: "
                "the Reconciler executes exactly the queries you list. Only these tables exist: "
                "policy_clauses, denial_reasons, medical_records, eob, procedure_codes, "
                "claim_documents, icd10_codes, appeal_evidence, claim_facts. "
                "Queries must be read-only SELECTs. Answer with JSON: "
                "{sources: [table], steps: [string], queries: [{id, sql, why}], "
                "claim_to_test: string, assumptions: [string]}. "
                "Never invent a document, quote, date or figure."
            ),
        },
        {"role": "user", "content": _json({"case": case, "policy": policy, "recalled_memory": memory})},
    ]


def reconciler_messages(summary: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are the Reconciler. Review this evidence-normalisation summary for mistakes: "
                "double counting, wrong dates, a missing required document presented as present. "
                "You cannot change the ledger. Answer with JSON {accepted: bool, issues: [string], notes: string}. "
                "Do not invent data."
            ),
        },
        {"role": "user", "content": _json(summary)},
    ]


def critic_conflict_messages(findings: list[dict[str, Any]], summary: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are the Critic in mode conflict_check. Review the candidate denial-reason findings "
                "produced by the evidence detectors. Confirm only findings the evidence supports; never "
                "invent a conflict. Each confirmed finding keeps its re-query SQL and action. Answer with JSON: "
                "{confirmed_indices: [int], dismissed_indices: [int], notes: string}. "
                "A missing required document must stay missing; do not propose fabricating it."
            ),
        },
        {"role": "user", "content": _json({"candidate_findings": findings, "summary": summary})},
    ]


def critic_adversarial_messages(claim: dict[str, Any], stats: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are the Critic in mode adversarial_review. Try to disprove the appeal. Attack the "
                "evidence, the citations, the missing documents and the policy version. Only break the "
                "claim if the file cannot support the appeal as written. If a re-query can settle it, return one. "
                "Answer with JSON: {attacks: [{claim, evidence, severity}], breaks_claim: bool, "
                "requery: {sql, action, why} | null, notes: string}. Re-query SQL must be read-only."
            ),
        },
        {"role": "user", "content": _json({"claim": claim, "stats": stats})},
    ]


def advocate_messages(claim: dict[str, Any], stats: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are the Advocate for the insurer. Your only job is to defend the denial and break "
                "the appeal: the exclusion applies, the code was wrong, the record is insufficient, the "
                "required letter is missing. Be specific. If the appeal survives your strongest reading "
                "of the policy, say so. Answer with JSON: {attacks: [{claim, evidence, severity}], "
                "breaks_claim: bool, requery: {sql, action, why} | null, rebuttals_needed: [string]}."
            ),
        },
        {"role": "user", "content": _json({"claim": claim, "stats": stats})},
    ]


def reporter_messages(facts: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are the Reporter. Draft the cover letter and the reason-by-reason rebuttal for an "
                "internal insurance appeal. Use only the supplied facts. Quote only text that appears in "
                "the facts. Every number must appear in the facts. If a required document is missing, say "
                "it is missing and add it to the checklist; never invent it. Do not give medical or legal "
                "advice or predict the insurer's decision. Answer with JSON: "
                "{cover_letter: string, rebuttals: [{reason_id, text}], limitations: [string]}."
            ),
        },
        {"role": "user", "content": _json(facts)},
    ]
