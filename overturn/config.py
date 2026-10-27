"""OVERTURN settings and mode resolution.

SAMPLE_MODE:
  true  -> offline: SQLite mirror + deterministic agents, no credentials.
  false -> live: Zetaris + Meterless Nightshift + Meterless engines.
  auto  -> offline when credentials are missing or still placeholders.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FIXTURES = DATA / "fixtures"
SOURCES = DATA / "sources"

PLACEHOLDER_MARKERS = ("placeholder", "changeme", "example.invalid")


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
    except Exception:
        pass


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    lowered = value.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def _nightshift_base() -> str:
    value = (os.getenv("NIGHTSHIFT_BASE_URL") or os.getenv("METERLESS_BASE_URL") or "").strip().rstrip("/")
    if not value:
        return ""
    if not value.endswith("/v1") and "/v1/" not in value:
        return value + "/v1"
    return value


def _zetaris_rest() -> str:
    return (
        os.getenv("ZETARIS_REST_URL")
        or os.getenv("ZETARIS_BASE_URL")
        or "http://localhost:3000"
    ).strip().rstrip("/")


def _zetaris_sql_path(rest: str) -> str:
    explicit = (os.getenv("ZETARIS_SQL_PATH") or "").strip()
    if explicit:
        return explicit
    return "/sql-editor/sqls/run" if ":8888" in rest else "/api/proxy/sql-editor/sqls/run-query"


@dataclass(frozen=True)
class Settings:
    offline: bool
    sample_mode_raw: str
    case_id: str = "ava"

    # Zetaris (the only data path)
    zetaris_rest_url: str = "http://localhost:3000"
    zetaris_org_id: str = "1"
    zetaris_api_key: str = ""
    zetaris_username: str = ""
    zetaris_password: str = ""
    zetaris_sql_path: str = "/api/proxy/sql-editor/sqls/run-query"
    zetaris_limit: int = 1000
    zetaris_timeout: float = 60.0
    zetaris_jdbc_url: str = ""
    zetaris_jdbc_jar: str = ""

    # Meterless Nightshift (OpenAI-compatible)
    nightshift_base_url: str = "http://127.0.0.1:8088/v1"
    nightshift_api_key: str = ""
    nightshift_app: str = "overturn"
    nightshift_scope: str = "user"
    nightshift_timeout: float = 120.0
    models: dict[str, str] = field(default_factory=dict)

    # Meterless engines
    hmem_url: str = ""
    hmem_api_key: str = ""
    world_model_url: str = ""
    world_model_api_key: str = ""

    hmem_store: str = str(ROOT / ".overturn" / "hmem.json")

    @property
    def sample_db(self) -> Path:
        return FIXTURES / "sample.db"

    @property
    def hmem_path(self) -> Path:
        return Path(self.hmem_store)

    @property
    def mode_label(self) -> str:
        return "sample" if self.offline else "live"

    @property
    def live_ready(self) -> bool:
        return not self.offline


def load_settings(mode_override: str | None = None) -> Settings:
    _load_dotenv()
    raw = (mode_override or os.getenv("SAMPLE_MODE", "auto")).strip().lower()

    rest = _zetaris_rest()
    api_key = os.getenv("ZETARIS_API_KEY", "").strip()
    username = os.getenv("ZETARIS_USERNAME", "").strip()
    password = os.getenv("ZETARIS_PASSWORD", "").strip()
    base = _nightshift_base()
    ns_key = (
        os.getenv("NIGHTSHIFT_API_KEY")
        or os.getenv("METERLESS_RUNTIME_TOKEN")
        or ""
    ).strip()

    zetaris_missing = not rest or (not api_key and not (username and password))
    missing_live = zetaris_missing or not base or not ns_key

    if raw in {"1", "true", "yes", "on", "sample"}:
        offline = True
    elif raw in {"0", "false", "no", "off", "live"}:
        if missing_live:
            raise RuntimeError(
                "SAMPLE_MODE=false was requested but the live stack is not configured. "
                "Set ZETARIS_REST_URL + ZETARIS_API_KEY (or username/password) and "
                "METERLESS_BASE_URL + METERLESS_RUNTIME_TOKEN, or run with --sample."
            )
        offline = False
    else:
        offline = missing_live

    fallback_model = os.getenv("METERLESS_MODEL", "meterless/auto").strip() or "meterless/auto"
    nemotron = os.getenv("NEMOTRON_MODEL", "").strip()
    models = {
        "planner": os.getenv("MODEL_PLANNER", "").strip() or fallback_model,
        "reconciler": os.getenv("MODEL_RECONCILER", "").strip() or fallback_model,
        "critic": os.getenv("MODEL_CRITIC", "").strip() or nemotron or fallback_model,
        "advocate": os.getenv("MODEL_ADVOCATE", "").strip() or nemotron or fallback_model,
        "reporter": os.getenv("MODEL_REPORTER", "").strip() or fallback_model,
        "nemotron": nemotron,
    }
    if nemotron:
        models["critic"] = nemotron
        models["advocate"] = nemotron

    return Settings(
        offline=offline,
        sample_mode_raw=raw,
        case_id=os.getenv("OVERTURN_CASE", "ava"),
        zetaris_rest_url=rest,
        zetaris_org_id=os.getenv("ZETARIS_ORG_ID", "1").strip() or "1",
        zetaris_api_key=api_key,
        zetaris_username=username,
        zetaris_password=password,
        zetaris_sql_path=_zetaris_sql_path(rest),
        zetaris_limit=int(os.getenv("ZETARIS_QUERY_LIMIT", "1000")),
        zetaris_timeout=float(os.getenv("ZETARIS_TIMEOUT_SECONDS", "60")),
        zetaris_jdbc_url=os.getenv("ZETARIS_JDBC_URL", "").strip(),
        zetaris_jdbc_jar=os.getenv("ZETARIS_JDBC_JAR", "").strip(),
        nightshift_base_url=base,
        nightshift_api_key=ns_key,
        nightshift_app=os.getenv("METERLESS_APP", "overturn").strip() or "overturn",
        nightshift_scope=os.getenv("METERLESS_SCOPE", "user").strip() or "user",
        nightshift_timeout=float(os.getenv("NIGHTSHIFT_TIMEOUT_SECONDS", "120")),
        models=models,
        hmem_url=(os.getenv("HMEM_URL", "") or "").strip().rstrip("/"),
        hmem_api_key=os.getenv("HMEM_API_KEY", ""),
        world_model_url=(os.getenv("WORLD_MODEL_URL", "") or "").strip().rstrip("/"),
        world_model_api_key=os.getenv("WORLD_MODEL_API_KEY", ""),
        hmem_store=os.getenv("OVERTURN_HMEM_PATH", str(ROOT / ".overturn" / "hmem.json")),
    )
