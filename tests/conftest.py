from __future__ import annotations

from dataclasses import replace

import pytest

from overturn.config import load_settings
from overturn.run import _load_case, run_pipeline
from overturn.trace import Tracer


@pytest.fixture(scope="session")
def base_settings():
    return load_settings("true")


@pytest.fixture(scope="session")
def case():
    return _load_case("ava")


@pytest.fixture(scope="session")
def pipeline(base_settings, case, tmp_path_factory):
    out = tmp_path_factory.mktemp("overturn-pipeline")
    settings = replace(base_settings, hmem_store=str(out / "hmem.json"))
    tracer = Tracer(out / "trace.jsonl")
    return run_pipeline(case, settings, out, tracer)
