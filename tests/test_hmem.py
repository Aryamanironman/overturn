"""Run 2 must recall the appeal and insurer patterns from run 1."""

from __future__ import annotations

from dataclasses import replace

from overturn.run import run_pipeline
from overturn.trace import Tracer


def _recall(events):
    return next(event for event in events if event["step"] == "memory_recall")


def test_second_run_recalls_first(base_settings, case, tmp_path):
    settings = replace(base_settings, hmem_store=str(tmp_path / "hmem.json"))

    run1_dir = tmp_path / "run1"
    run1 = run_pipeline(case, settings, run1_dir, Tracer(run1_dir / "trace.jsonl"))
    assert _recall(run1["trace"])["memory"] == []

    run2_dir = tmp_path / "run2"
    run2 = run_pipeline(case, settings, run2_dir, Tracer(run2_dir / "trace.jsonl"))
    recalled = _recall(run2["trace"])["memory"]
    assert recalled
    kinds = {item["kind"] for item in recalled}
    assert {"appeal_pattern", "insurer_pattern"} <= kinds
    texts = " ".join(item["text"] for item in recalled)
    assert "appeal strength 84" in texts
    assert "Northbridge Health denial pattern" in texts
