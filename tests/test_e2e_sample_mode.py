"""Fresh clone, one command, no credentials, under 60 seconds."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from overturn.config import ROOT
from overturn.reporter import verify_chain
from overturn.router import route_request
from overturn.scorer import score_appeal


def test_cli_runs_offline_and_writes_a_computed_packet(tmp_path):
    out = tmp_path / "out"
    env = os.environ.copy()
    env["SAMPLE_MODE"] = "true"
    env["OVERTURN_HMEM_PATH"] = str(tmp_path / "hmem.json")
    started = time.perf_counter()
    process = subprocess.run(
        [sys.executable, "-m", "overturn.run", "--case", "ava", "--out", str(out)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    elapsed = time.perf_counter() - started
    assert process.returncode == 0, process.stderr
    assert elapsed < 60

    for name in ("appeal_packet.json", "appeal_packet.md", "receipt.html", "trace.jsonl"):
        assert (out / name).exists(), f"missing {name}"

    packet = json.loads((out / "appeal_packet.json").read_text(encoding="utf-8"))
    assert packet["appeal_strength"]["score"] == 84
    assert packet["appeal_strength"]["status"] == "conditional"
    assert len(packet["denial_reasons"]) == 4
    assert verify_chain(packet["evidence"], packet["provenance"]["head_hash"])

    case = json.loads((ROOT / "input_examples" / "ava_request.json").read_text(encoding="utf-8"))
    policy = route_request(case["request"], case["purpose"])
    recomputed = score_appeal(
        packet["denial_reasons"], packet["evidence"], packet["claim"], case["as_of"], policy
    )
    assert recomputed["score"] == packet["appeal_strength"]["score"]

    trace = [
        json.loads(line) for line in (out / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert sum(1 for event in trace if event["step"] == "requery_exec") == 5
    assert any(event["step"] == "agent_call" and event.get("model") for event in trace)

    serialised = " ".join(
        (out / name).read_text(encoding="utf-8")
        for name in ("appeal_packet.json", "appeal_packet.md", "receipt.html", "trace.jsonl")
    )
    assert "ZETARIS_API_KEY" not in serialised
    assert "METERLESS_RUNTIME_TOKEN" not in serialised
