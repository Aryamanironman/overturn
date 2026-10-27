"""Zetaris Lightning JDBC client for live mode.

The REST UI proxy is not reachable from this environment, but the cluster's
JDBC endpoint is. This client runs the same read-only SQL through the Zetaris
drivers and qualifies the known tables with the OVERTURN_DB database, because
the JDBC session does not inherit the UI's default database.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from .config import Settings
from .trace import Tracer
from .zetaris import validate_read_only

TABLES = (
    "policy_clauses|denial_reasons|medical_records|eob|procedure_codes|"
    "claim_documents|icd10_codes|appeal_evidence|claim_facts|"
    "usl_claim_review|dq_claim_integrity"
)
QUALIFY = re.compile(
    rf"\b(FROM|JOIN)\s+(?!(?:OVERTURN_DB|overturn_db)\.)({TABLES})\b",
    re.IGNORECASE,
)


class JdbcClient:
    engine = "zetaris-jdbc"

    def __init__(self, settings: Settings, tracer: Tracer) -> None:
        self.settings = settings
        self.tracer = tracer
        self._conn: Any = None
        self._stmt: Any = None

    def _connect(self) -> None:
        if self._conn is not None:
            return
        import jpype
        import jpype.imports  # noqa: F401

        jar = self.settings.zetaris_jdbc_jar
        if not jar or not Path(jar).exists():
            raise RuntimeError(f"ZETARIS_JDBC_JAR not found: {jar}")
        java = shutil.which("java") or "java"
        home = Path(java).resolve().parents[1]
        os.environ["JAVA_HOME"] = str(home)
        os.environ["PATH"] = str(home / "bin") + os.pathsep + os.environ.get("PATH", "")
        cacerts = str(home / "lib" / "security" / "cacerts")
        jvm = home / "bin" / "server" / "jvm.dll"
        if not jpype.isJVMStarted():
            jpype.startJVM(
                str(jvm) if jvm.exists() else jpype.getDefaultJVMPath(),
                f"-Djavax.net.ssl.trustStore={cacerts}",
                "-Djavax.net.ssl.trustStorePassword=changeit",
                classpath=[jar],
                convertStrings=True,
            )
        from java.lang import Class
        from java.sql import DriverManager
        from java.util import Properties

        Class.forName("com.zetaris.lightning.jdbc.LightningDriver")
        props = Properties()
        values = {
            "user": self.settings.zetaris_username,
            "password": self.settings.zetaris_password,
            "ssl": "true",
            "trustStore": cacerts,
            "trustStorePassword": "changeit",
            "trustStoreType": "JKS",
            "sslTrustStore": cacerts,
            "sslTrustStorePassword": "changeit",
            "sslTrustStoreType": "JKS",
        }
        for key, value in values.items():
            props.setProperty(key, value)
        self._conn = DriverManager.getConnection(self.settings.zetaris_jdbc_url, props)
        self._stmt = self._conn.createStatement()

    def run_sql(self, sql: str, agent: str = "reconciler") -> list[dict[str, Any]]:
        validated = validate_read_only(sql)
        rewritten = QUALIFY.sub(lambda m: f"{m.group(1)} OVERTURN_DB.{m.group(2)}", validated)
        self._connect()
        result = self._stmt.executeQuery(rewritten)
        meta = result.getMetaData()
        columns = [
            (meta.getColumnName(index + 1), meta.getColumnType(index + 1))
            for index in range(meta.getColumnCount())
        ]
        rows: list[dict[str, Any]] = []
        while result.next():
            row: dict[str, Any] = {}
            for index, (name, jdbc_type) in enumerate(columns, 1):
                row[name] = self._convert(result.getObject(index), jdbc_type)
            rows.append(row)
        preview = [{key: row[key] for key in list(row)[:8]} for row in rows[:3]]
        self.tracer.event(
            "sql",
            agent=agent,
            engine=self.engine,
            sql=validated,
            rows=len(rows),
            rows_preview=preview,
        )
        return rows

    @staticmethod
    def _convert(value: Any, jdbc_type: int) -> Any:
        if value is None:
            return None
        from java.sql import Types

        integers = {Types.INTEGER, Types.SMALLINT, Types.TINYINT, Types.BIGINT}
        floats = {Types.DOUBLE, Types.FLOAT, Types.REAL, Types.DECIMAL, Types.NUMERIC}
        booleans = {Types.BOOLEAN, Types.BIT}
        try:
            if jdbc_type in integers:
                return int(value)
            if jdbc_type in floats:
                return float(value)
            if jdbc_type in booleans:
                return bool(value)
            return str(value)
        except Exception:
            return str(value)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
                self._stmt = None
