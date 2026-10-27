"""Render out/receipt.html: the appeal evidence map.

A self-contained page: no external scripts, fonts, images or network calls.
"""

from __future__ import annotations

import html
from typing import Any

from .reporter import verify_chain

CSS = """
:root{
  --paper:#eef1f4; --panel:#f8fafc; --ink:#10202b; --muted:#5f6d79; --rule:#c9d2dc;
  --blue:#1d4ed8; --green:#1b6b4a; --amber:#8a5a12; --red:#b3261e;
  --sans:ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 var(--sans)}
main{max-width:1180px;margin:0 auto;padding:36px 24px 70px}
header.top{display:flex;justify-content:space-between;gap:30px;align-items:flex-end;border-bottom:2px solid var(--ink);padding-bottom:18px}
.kicker{font:12px/1.4 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
h1{font:650 42px/1.05 var(--sans);letter-spacing:-.03em;margin:8px 0 6px;max-width:18ch}
.sub{max-width:70ch;color:#3c4b57;margin:0}
.verdict{text-align:right;min-width:210px}
.verdict b{display:block;font:650 54px/1 var(--sans);letter-spacing:-.04em}
.verdict span{display:block;font:12px/1.4 var(--mono);color:var(--muted);margin-top:4px}
.verdict .status{display:inline-block;margin-top:8px;padding:4px 8px;border:1px solid var(--amber);color:var(--amber);font:12px/1 var(--mono);text-transform:uppercase;letter-spacing:.05em}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);border-bottom:1px solid var(--ink);margin:22px 0 28px}
.kpis div{padding:12px 16px 14px 0;border-right:1px solid var(--rule)}
.kpis div:last-child{border-right:0}
.kpis small{display:block;font:12px/1.4 var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
.kpis strong{font:650 24px/1.1 var(--sans)}
.kpis em{display:block;font-style:normal;font-size:12px;color:var(--muted);margin-top:2px}
h2{font:650 22px/1.2 var(--sans);letter-spacing:-.01em;margin:34px 0 12px}
h3{font:600 16px/1.3 var(--sans);margin:0 0 5px}
.card{background:var(--panel);border:1px solid var(--rule);border-left:4px solid var(--green);padding:13px 15px;margin-bottom:10px}
.card.missing{border-left-color:var(--amber)}
.card.open{border-left-color:var(--red)}
.card .meta{font:12px/1.4 var(--mono);color:var(--muted);margin-bottom:4px}
.card .rebuttal{font-size:14px;color:#344551;margin:4px 0 4px}
.card .sources{font:12px/1.5 var(--mono);color:var(--muted);word-break:break-word}
.chip{display:inline-block;font:12px/1 var(--mono);text-transform:uppercase;letter-spacing:.04em;padding:3px 6px;border:1px solid currentColor;border-radius:2px}
.chip.rebutted{color:var(--green)} .chip.missing{color:var(--amber)} .chip.open{color:var(--red)}
table{width:100%;border-collapse:collapse;background:var(--panel);font-size:14px}
th{text-align:left;font:600 12px/1.4 var(--mono);text-transform:uppercase;letter-spacing:.03em;color:var(--muted);border-bottom:1px solid var(--ink);padding:8px 8px 6px 0}
td{border-bottom:1px solid var(--rule);padding:8px 8px 8px 0;vertical-align:top}
td.num,th.num{text-align:right;font-family:var(--mono);white-space:nowrap}
.mono{font-family:var(--mono);font-size:12.5px}
.muted{color:var(--muted)}
.note{border-left:3px solid var(--amber);background:#fbf4e6;padding:12px 14px;margin:14px 0}
.note b{display:block;margin-bottom:3px}
.timeline{border-left:2px solid var(--rule);margin-left:6px;padding-left:16px}
.hop{position:relative;padding:7px 0 9px}
.hop::before{content:"";position:absolute;left:-22px;top:15px;width:8px;height:8px;background:var(--ink);border-radius:50%}
.hop .who{font-weight:600}
.hop .meta{font:12px/1.45 var(--mono);color:var(--muted)}
footer{margin-top:42px;border-top:2px solid var(--ink);padding-top:12px;font:12px/1.6 var(--mono);color:var(--muted);word-break:break-word}
@media (max-width:820px){main{padding:22px 16px}header.top{flex-direction:column;align-items:flex-start}.verdict{text-align:left}.kpis{grid-template-columns:1fr 1fr}}
"""


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def render(packet: dict[str, Any], events: list[dict[str, Any]]) -> str:
    strength = packet["appeal_strength"]
    claim = packet["claim"]
    case = packet["case"]
    chain_ok = verify_chain(packet["evidence"], packet["provenance"]["head_hash"])
    counts = strength["counts"]
    missing = packet.get("missing_documents", [])
    agent_calls = [event for event in events if event.get("step") == "agent_call"]
    requeries = [event for event in events if event.get("step") == "requery_exec"]

    parts: list[str] = []
    parts.append("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">")
    parts.append("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">")
    parts.append(f"<title>OVERTURN — {_e(case.get('case_id'))} appeal evidence map</title>")
    parts.append(f"<style>{CSS}</style></head><body><main>")

    parts.append("<header class=\"top\"><div><div class=\"kicker\">OVERTURN / internal appeal / evidence map</div>")
    parts.append(f"<h1>The denial, answered with evidence.</h1>")
    parts.append(f"<p class=\"sub\">{_e(case.get('claimant', {}).get('name'))} · {_e(case.get('insurer'))} · claim {_e(claim.get('claim_id'))} · denial {_e(claim.get('denial_date'))} · appeal due {_e(claim.get('appeal_deadline'))}</p></div>")
    parts.append(f"<div class=\"verdict\"><b>{_e(strength['score'])}</b><span>appeal strength / 100</span><span>{_e(strength['bucket'])}</span><span class=\"status\">{_e(strength['status'])}</span></div></header>")

    parts.append("<section class=\"kpis\">")
    for label, value, note in [
        ("Reasons rebutted", f"{counts['rebutted']} / {counts['reason_count']}", "with at least two citations"),
        ("Missing documents", str(len(missing)), "required; not fabricated"),
        ("Evidence lines", str(packet["provenance"]["line_count"]), "hashed provenance"),
        ("Re-queries", str(len(requeries)), "executed by the Reconciler"),
    ]:
        parts.append(f"<div><small>{_e(label)}</small><strong>{_e(value)}</strong><em>{_e(note)}</em></div>")
    parts.append("</section>")

    if missing:
        parts.append("<div class=\"note\"><b>Send this first.</b>")
        for item in missing:
            parts.append(f"{_e(item.get('name'))} ({_e(item.get('document_id'))}) — required by {_e(item.get('required_by'))}. {_e(item.get('note'))}")
        parts.append("</div>")

    parts.append("<h2>Why the denial is wrong</h2>")
    for reason in packet["denial_reasons"]:
        status = reason.get("status", "open")
        parts.append(f"<div class=\"card {_e(status if status in {'missing','open'} else '')}\">")
        parts.append(f"<div class=\"meta\">{_e(reason.get('reason_id'))} · <span class=\"chip {_e(status)}\">{_e(status)}</span></div>")
        parts.append(f"<h3>{_e(reason.get('reason_text'))}</h3>")
        if reason.get("rebuttal"):
            parts.append(f"<div class=\"rebuttal\">{_e(reason['rebuttal'])}</div>")
        sources = ", ".join(item["source"] for item in reason.get("citations", [])) or "—"
        parts.append(f"<div class=\"sources\">sources: {_e(sources)}</div>")
        parts.append("</div>")

    parts.append("<h2>Evidence ledger</h2>")
    parts.append("<table><thead><tr><th>Line</th><th>Source</th><th>Date</th><th>Summary</th><th>Status</th><th>Hash</th></tr></thead><tbody>")
    for line in packet["evidence"]:
        parts.append(
            f"<tr><td class=\"mono\">{_e(line['line_id'])}</td>"
            f"<td class=\"mono\">{_e(line['source_table'])}:{_e(line['source_row_id'])}</td>"
            f"<td class=\"mono\">{_e(line.get('date'))}</td>"
            f"<td>{_e(line.get('summary'))}</td>"
            f"<td class=\"mono\">{_e(line.get('verification_status'))}</td>"
            f"<td class=\"mono muted\">{_e(line['hash'][:10])}…</td></tr>"
        )
    parts.append("</tbody></table>")

    parts.append("<h2>Counterfactuals</h2>")
    parts.append("<table><thead><tr><th>Removed source</th><th class=\"num\">Strength</th><th class=\"num\">Change</th><th class=\"num\">Reasons rebutted</th></tr></thead><tbody>")
    for item in packet["counterfactuals"]:
        parts.append(
            f"<tr><td class=\"mono\">{_e(item['removed_source'])}</td>"
            f"<td class=\"num\">{item['score_before']} → {item['score_after']}</td>"
            f"<td class=\"num\">{item['score_delta']:+d}</td>"
            f"<td class=\"num\">{item['rebutted_before']} → {item['rebutted_after']}</td></tr>"
        )
    parts.append("</tbody></table>")

    parts.append("<h2>Who touched the appeal</h2>")
    parts.append("<table><thead><tr><th>Agent</th><th>Mode</th><th>Model</th><th class=\"num\">Latency</th><th>Decision</th></tr></thead><tbody>")
    for event in agent_calls:
        parts.append(
            f"<tr><td>{_e(event.get('agent'))}</td><td class=\"mono\">{_e(event.get('mode'))}</td>"
            f"<td class=\"mono\">{_e(event.get('model'))}</td>"
            f"<td class=\"num\">{_e(event.get('latency_ms'))} ms</td>"
            f"<td class=\"muted\">{_e(event.get('decision'))}</td></tr>"
        )
    parts.append("</tbody></table>")

    parts.append("<h2>Reasoning trace</h2><div class=\"timeline\">")
    interesting = {"run_start","route","memory_recall","plan","reconcile","agent_call","sql","critic_findings","requery_exec","conflict_update","adversarial_review","advocate_review","exclusion","score","counterfactual","report","run_end","loop_cap","escalation","memory_write","reporter_validation"}
    for event in events:
        if event.get("step") not in interesting:
            continue
        meta = " · ".join(str(x) for x in (event.get("step"), event.get("mode"), event.get("model"), event.get("latency_ms")) if x)
        parts.append(f"<div class=\"hop\"><div class=\"who\">{_e(event.get('agent') or 'system')}</div>")
        parts.append(f"<div class=\"meta\">{_e(meta)}</div>")
        if event.get("decision"):
            parts.append(f"<div>{_e(event['decision'])}</div>")
        if event.get("sql"):
            parts.append(f"<div class=\"meta\">SQL: {_e(event['sql'])} · {_e(event.get('rows'))} rows</div>")
        parts.append("</div>")
    parts.append("</div>")

    parts.append("<footer>")
    parts.append(f"SHA-256 chain over {packet['provenance']['line_count']} evidence lines. Head <span class=\"mono\">{_e(packet['provenance']['head_hash'])}</span>. Chain verified in this render: <b>{'yes' if chain_ok else 'NO'}</b>. ")
    parts.append("This is an evidence-strength assessment, not a prediction of the insurer's decision. A human must review and sign the packet.")
    parts.append("</footer></main></body></html>")
    return "".join(parts)
