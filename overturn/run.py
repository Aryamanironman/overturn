"""CLI entrypoint and control loop.

    python -m overturn.run --case ava --out out/

The loop is a state machine:
  planner -> reconciler -> critic(conflict_check)
    open denial reasons and iteration < 4 -> reconciler re-queries
  critic(adversarial_review) + advocate
    appeal broken and iteration < 3 -> reconciler re-queries
  unresolved after the cap -> one human escalation
  scorer -> reporter -> appeal packet
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from .advocate import Advocate
from .config import ROOT, Settings, load_settings
from .critic import Critic
from .hmem import LocalHMem, make_hmem
from .llm import LLMClient
from .planner import Planner
from .receipt import render as render_receipt
from .reconciler import Reconciler
from .reporter import Reporter, write_packet_json, write_packet_md
from .router import route_request
from .scorer import counterfactuals, score_appeal
from .trace import Tracer
from .world_model import WorldModel, make_world_model
from .zetaris import SqlClient

MAX_CONFLICT_ITERS = 4
MAX_ADVOCATE_ITERS = 3
MAX_ESCALATIONS = 1
MAX_LINE_ITERATIONS = MAX_CONFLICT_ITERS + MAX_ADVOCATE_ITERS + MAX_ESCALATIONS


def _load_case(name: str) -> dict[str, Any]:
    candidate = Path(name)
    if candidate.suffix == ".json" and candidate.exists():
        path = candidate
    else:
        path = ROOT / "input_examples" / f"{name}_request.json"
    if not path.exists():
        raise FileNotFoundError(f"case file not found: {path}")
    case = json.loads(path.read_text(encoding="utf-8"))
    for field in ("case_id", "claimant", "insurer", "claim_id", "request"):
        if field not in case:
            raise ValueError(f"case file missing '{field}': {path}")
    case.setdefault("as_of", date.today().isoformat())
    case.setdefault("appeal_deadline", "")
    return case


def _human_question(conflicts: list[dict[str, Any]]) -> str:
    conflict = conflicts[0]
    return (
        f"The insurer's reason {conflict.get('reason_id')} is still unresolved. "
        "Which document or policy clause settles it? Answer in one sentence."
    )


def _escalation_answer(settings: Settings, question: str, tracer: Tracer) -> str:
    if not settings.offline:
        return input(question + "\n> ").strip()
    fixture = ROOT / "data" / "fixtures" / "escalation_answers.json"
    answers: list[str] = []
    if fixture.exists():
        try:
            answers = json.loads(fixture.read_text(encoding="utf-8")).get("escalation_answers", [])
        except json.JSONDecodeError:
            answers = []
    asked = max(0, sum(1 for event in tracer.events if event.get("step") == "escalation") - 1)
    if answers:
        return answers[min(asked, len(answers) - 1)]
    return "Treat the reason as unresolved and keep the packet conditional."


def _remember_run(
    hmem: LocalHMem,
    case: dict[str, Any],
    world: WorldModel,
    score: dict[str, Any],
    tracer: Tracer,
) -> None:
    reasons = [item for item in world.conflicts() if item.get("kind") == "denial_reason"]
    rebutted = [item for item in reasons if item.get("status") == "rebutted"]
    missing = [item for item in reasons if item.get("status") == "missing"]
    pattern = (
        f"Appeal for {case['claimant'].get('name')} against {case['insurer']}: "
        f"{len(rebutted)} of {len(reasons)} reasons rebutted, {len(missing)} missing document; "
        f"appeal strength {score['score']} ({score['bucket']}, {score['status']})."
    )
    item = hmem.remember(case["case_id"], "appeal_pattern", pattern, {"case_id": case["case_id"]})
    insurer = hmem.remember(
        case["case_id"],
        "insurer_pattern",
        (
            f"{case['insurer']} denial pattern: "
            + "; ".join(
                f"{reason.get('reason_id')} {reason.get('finding_kind') or reason.get('status')}"
                for reason in reasons
            )
        ),
        {"insurer": case["insurer"]},
    )
    tracer.event(
        "memory_write",
        agent="hmem",
        engine=hmem.engine,
        decision="2 memory item(s) written",
        memory_ids=[item["memory_id"], insurer["memory_id"]],
    )


def run_conflict_loop(
    world: WorldModel,
    critic: Critic,
    reconciler: Reconciler,
    case: dict[str, Any],
    settings: Settings,
    tracer: Tracer,
) -> dict[str, Any]:
    iteration = 0
    escalations = 0
    requeries = 0
    while iteration < MAX_LINE_ITERATIONS:
        critic.conflict_check(world, iteration)
        open_reasons = [
            item for item in world.conflicts()
            if item.get("kind") == "denial_reason" and item.get("status") == "open"
        ]
        if not open_reasons:
            break
        if iteration >= MAX_CONFLICT_ITERS:
            if escalations >= MAX_ESCALATIONS:
                tracer.event(
                    "loop_cap",
                    agent="system",
                    decision=f"conflict cap reached with {len(open_reasons)} open reason(s)",
                    iteration=iteration,
                )
                break
            question = _human_question(open_reasons)
            tracer.event("escalation", agent="human", decision=question, iteration=iteration)
            answer = _escalation_answer(settings, question, tracer)
            reconciler.requery(
                world,
                {
                    "sql": open_reasons[0].get("requery_sql") or "SELECT 1",
                    "action": {
                        "type": "apply_human_answer",
                        "answer": answer,
                        "conflict_ids": [item["conflict_id"] for item in open_reasons],
                    },
                    "why": "human escalation answer",
                },
            )
            requeries += 1
            escalations += 1
            iteration += 1
            reconciler.refresh_claim(world, case)
            continue

        for conflict in open_reasons:
            instruction = {
                "sql": conflict.get("requery_sql", ""),
                "action": conflict.get("action", {}),
                "conflict_id": conflict["conflict_id"],
                "why": conflict.get("question", "critic re-query"),
            }
            try:
                reconciler.requery(world, instruction)
                requeries += 1
            except Exception as exc:
                tracer.event(
                    "requery_error",
                    agent="reconciler",
                    decision=str(exc),
                    conflict_id=conflict["conflict_id"],
                    iteration=iteration,
                )
                world.update_conflict(
                    conflict["conflict_id"], status="open", last_error=str(exc), _agent="system"
                )
        iteration += 1
        reconciler.refresh_claim(world, case)
    return {"iterations": iteration, "escalations": escalations, "requeries": requeries}


def run_adversarial_loop(
    world: WorldModel,
    critic: Critic,
    advocate: Advocate,
    reconciler: Reconciler,
    case: dict[str, Any],
    tracer: Tracer,
) -> dict[str, Any]:
    adv_iteration = 0
    reviews: dict[str, Any] = {"critic": {}, "advocate": {}}
    requeries = 0
    while adv_iteration < MAX_ADVOCATE_ITERS:
        claim = world.claim()
        critic_review = critic.adversarial_review(world, claim, adv_iteration)
        advocate_review = advocate.review(world, claim, adv_iteration)
        reviews = {"critic": critic_review, "advocate": advocate_review}
        breaker = None
        if critic_review.get("breaks_claim"):
            breaker = critic_review
        elif advocate_review.get("breaks_claim"):
            breaker = advocate_review
        if not breaker:
            break
        requery = breaker.get("requery")
        if not requery:
            tracer.event(
                "adversarial_stop",
                agent="advocate",
                decision="appeal broken but no re-query could settle it",
                iteration=adv_iteration,
            )
            break
        if adv_iteration >= MAX_ADVOCATE_ITERS - 1:
            tracer.event(
                "loop_cap",
                agent="system",
                decision="advocate cap reached with the appeal still contested",
                iteration=adv_iteration,
            )
            break
        reconciler.requery(
            world,
            {"sql": requery["sql"], "action": requery["action"], "why": requery.get("why", "adversary re-query")},
        )
        requeries += 1
        reconciler.refresh_claim(world, case)
        adv_iteration += 1
    return {"iterations": adv_iteration, "reviews": reviews, "requeries": requeries}


def run_pipeline(
    case: dict[str, Any],
    settings: Settings,
    out_dir: Path,
    tracer: Tracer | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tracer = tracer or Tracer(out_dir / "trace.jsonl")
    tracer.event(
        "run_start",
        agent="system",
        mode=settings.mode_label,
        decision=f"case {case['case_id']} as of {case['as_of']}",
        sample_mode_raw=settings.sample_mode_raw,
        zetaris=("sqlite-mirror" if settings.offline else settings.zetaris_rest_url),
        nightshift=("offline-deterministic" if settings.offline else settings.nightshift_base_url),
    )

    sql = SqlClient(settings, tracer)
    llm = LLMClient(settings, tracer, ROOT / "data" / "fixtures" / "llm_responses.jsonl")
    route = route_request(case.get("request", ""), case.get("purpose"))
    tracer.event(
        "route",
        agent="router",
        decision=f"{route['purpose']}: {route['classification_reason']}",
        policy={key: route[key] for key in ("purpose", "appeal_window_days", "stale_days")},
    )

    hmem = make_hmem(settings, tracer)
    memory = hmem.recall(case["case_id"], topics=["appeal", "denial", "insurer", "pattern"])
    tracer.event(
        "memory_recall",
        agent="hmem",
        engine=hmem.engine,
        decision=f"{len(memory)} prior memory item(s) recalled",
        memory=[{"memory_id": item.get("memory_id"), "kind": item.get("kind"), "text": item.get("text")} for item in memory],
    )

    world = make_world_model(settings, tracer, case["case_id"])
    planner = Planner(llm, tracer)
    reconciler = Reconciler(sql, llm, tracer)
    critic = Critic(llm, tracer)
    advocate = Advocate(llm, tracer)
    reporter = Reporter(llm, tracer)

    plan = planner.run(case, route, memory)
    reconciler.reconcile(world, plan, case)
    reconciler.refresh_claim(world, case)

    # ---- conflict loop -------------------------------------------------
    conflict_stats = run_conflict_loop(world, critic, reconciler, case, settings, tracer)

    # ---- adversarial loop ----------------------------------------------
    adversarial_stats = run_adversarial_loop(world, critic, advocate, reconciler, case, tracer)
    reviews = adversarial_stats["reviews"]
    tracer.event(
        "loop_summary",
        agent="system",
        decision=(
            f"conflict iterations {conflict_stats['iterations']}/{MAX_CONFLICT_ITERS}, "
            f"adversarial iterations {adversarial_stats['iterations']}/{MAX_ADVOCATE_ITERS}, "
            f"re-queries {conflict_stats['requeries'] + adversarial_stats['requeries']}"
        ),
        escalations=conflict_stats["escalations"],
    )

    # ---- score and counterfactuals -------------------------------------
    claim = world.claim()
    score = score_appeal(world.conflicts(), world.lines(), claim, case["as_of"], route)
    tracer.event(
        "score",
        agent="scorer",
        decision=(
            f"{score['score']}/100 {score['bucket']} {score['status']}: "
            f"{score['counts']['rebutted']} rebutted, {score['counts']['missing']} missing, "
            f"{score['counts']['unresolved']} unresolved"
        ),
        score=score["score"],
        bucket=score["bucket"],
        status=score["status"],
    )
    counter = counterfactuals(world.conflicts(), world.lines(), claim, case["as_of"], route)
    tracer.event(
        "counterfactual",
        agent="scorer",
        decision=f"{len(counter)} evidence sources removed in turn",
        deltas={item["removed_source"]: item["score_delta"] for item in counter},
    )

    packet = reporter.write(
        case=case,
        policy=route,
        plan=plan,
        claim=claim,
        world=world,
        score=score,
        counterfactuals=counter,
        reviews=reviews,
        routing=llm.routing_table(),
    )
    write_packet_json(packet, out_dir / "appeal_packet.json")
    write_packet_md(packet, out_dir / "appeal_packet.md")
    (out_dir / "receipt.html").write_text(render_receipt(packet, tracer.events), encoding="utf-8")

    _remember_run(hmem, case, world, score, tracer)
    tracer.event(
        "run_end",
        agent="system",
        decision=(
            f"packet written; strength {score['score']} ({score['bucket']}, {score['status']}); "
            f"head {packet['provenance']['head_hash'][:12]}"
        ),
        output=str(out_dir),
        conflict_statuses={item["conflict_id"]: item.get("status") for item in world.conflicts()},
    )
    return {
        "packet": packet,
        "score": score,
        "counterfactuals": counter,
        "trace": tracer.events,
        "out_dir": out_dir,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="overturn.run", description="OVERTURN appeal pipeline")
    parser.add_argument("--case", default="ava", help="case id under input_examples/ or a JSON case path")
    parser.add_argument("--out", default="out", help="output directory")
    parser.add_argument("--sample", action="store_true", help="force offline SAMPLE_MODE")
    parser.add_argument("--live", action="store_true", help="force live Zetaris + Nightshift")
    parser.add_argument("--reset-memory", action="store_true", help="clear the local H-MEM store")
    args = parser.parse_args(argv)
    if args.sample and args.live:
        parser.error("--sample and --live are mutually exclusive")
    mode_override = "true" if args.sample else "false" if args.live else None
    try:
        settings = load_settings(mode_override)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.reset_memory and settings.hmem_path.exists():
        settings.hmem_path.unlink()

    case = _load_case(args.case)
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    result = run_pipeline(case, settings, out_dir)
    packet = result["packet"]
    score = result["score"]
    print(f"OVERTURN — case {case['case_id']} — mode {settings.mode_label}")
    print(f"  appeal strength {score['score']}/100 ({score['bucket']}, {score['status']})")
    print(f"  reasons: {score['counts']['rebutted']} rebutted, {score['counts']['missing']} missing, "
          f"{score['counts']['unresolved']} unresolved")
    for reason in packet["denial_reasons"]:
        print(f"  {reason['reason_id']}: {reason['status']} — {reason.get('reason_text')}")
    if packet["missing_documents"]:
        for item in packet["missing_documents"]:
            print(f"  missing: {item['name']} ({item['document_id']})")
    print(f"  wrote {out_dir / 'appeal_packet.json'}")
    print(f"  wrote {out_dir / 'appeal_packet.md'}")
    print(f"  wrote {out_dir / 'receipt.html'}")
    print(f"  trace {out_dir / 'trace.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
