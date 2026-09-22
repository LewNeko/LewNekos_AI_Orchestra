"""
store.py
(was reader_result_store.py - unchanged, now in-package)

Canonical SQLite persistence for ReaderResult objects.

Design:
    ReaderResult -> SQLite (source of truth) -> derived indexes (e.g. vector DB)

This module deliberately does NOT:
- reinterpret Reader logic
- call an LLM
- calculate revisions
- decide whether a claim is supported
- maintain a vector database

It only persists the complete ReaderResult chain and its relationships.

The adapter is intentionally duck-typed so it does not require the exact
implementation of ReaderResult / FactClaim / Evidence / RevisionEvent /
SupportJudgment to live in this module.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS processing_runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS facts (
    fact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    document_id TEXT,
    chunk_id TEXT,
    question TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (run_id) REFERENCES processing_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_facts_document
    ON facts(document_id);

CREATE INDEX IF NOT EXISTS idx_facts_chunk
    ON facts(chunk_id);

CREATE INDEX IF NOT EXISTS idx_facts_question
    ON facts(question);

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL,
    claim_role TEXT NOT NULL,
    value TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (fact_id) REFERENCES facts(fact_id)
);

CREATE INDEX IF NOT EXISTS idx_claims_fact
    ON claims(fact_id);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL,
    claim_id TEXT,
    evidence_role TEXT NOT NULL,
    quote TEXT NOT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (fact_id) REFERENCES facts(fact_id),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_fact
    ON evidence(fact_id);

CREATE TABLE IF NOT EXISTS support_judgments (
    support_judgment_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL,
    judgment TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (fact_id) REFERENCES facts(fact_id)
);

CREATE INDEX IF NOT EXISTS idx_support_fact
    ON support_judgments(fact_id);

CREATE TABLE IF NOT EXISTS revisions (
    revision_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL,
    evidence_id TEXT,
    operation TEXT,
    amount TEXT,
    computed_value TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (fact_id) REFERENCES facts(fact_id),
    FOREIGN KEY (evidence_id) REFERENCES evidence(evidence_id)
);

CREATE INDEX IF NOT EXISTS idx_revisions_fact
    ON revisions(fact_id);

CREATE TABLE IF NOT EXISTS reader_results (
    result_id TEXT PRIMARY KEY,
    fact_id TEXT NOT NULL UNIQUE,
    raw_json TEXT NOT NULL,
    created_at TEXT NOT NULL,

    FOREIGN KEY (fact_id) REFERENCES facts(fact_id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _get(obj: Any, name: str, default: Any = None) -> Any:
    """Read an attribute from an object or key from a dict."""
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def _serialize(value: Any) -> Any:
    """
    Convert common Python/domain objects into JSON-safe values.

    This is primarily for the raw ReaderResult snapshot. It also makes the
    adapter tolerant of dataclasses, enums, dictionaries, lists, and simple
    domain objects without requiring their definitions here.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (datetime,)):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_serialize(v) for v in value]

    if isinstance(value, set):
        return [_serialize(v) for v in sorted(value, key=str)]

    # Enum-like objects.
    enum_value = getattr(value, "value", None)
    if enum_value is not None and enum_value is not value:
        return _serialize(enum_value)

    # Dataclasses and normal domain objects.
    if hasattr(value, "__dict__"):
        return {
            key: _serialize(val)
            for key, val in vars(value).items()
            if not key.startswith("_")
        }

    return str(value)


def _json(value: Any) -> str:
    return json.dumps(_serialize(value), ensure_ascii=False, sort_keys=True)


def _text(value: Any) -> Optional[str]:
    """Convert a domain value to text while preserving None."""
    if value is None:
        return None

    if isinstance(value, str):
        return value

    return str(_serialize(value))


class ReaderResultStore:
    """
    SQLite persistence layer for ReaderResult.

    Usage:

        store = ReaderResultStore("fact_history.db")

        run_id = store.start_run(
            document_id="invoice_001",
            metadata={"source": "reader"},
        )

        fact_id = store.save_result(
            result,
            run_id=run_id,
            document_id="invoice_001",
            chunk_id="chunk_004",
        )

        store.close()

    The database is the canonical structured record. A vector database should
    be built later from these rows rather than becoming another source of
    truth.
    """

    def __init__(self, db_path: str | Path = "fact_history.db"):
        self.db_path = str(db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "ReaderResultStore":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @contextmanager
    def transaction(self):
        """
        Execute a group of writes atomically.

        If anything fails, every write in the transaction is rolled back.
        """
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def start_run(
        self,
        document_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        run_id: Optional[str] = None,
    ) -> str:
        """
        Create a processing-run identity.

        A run represents one execution of the Reader against a document or
        collection of chunks. It gives every resulting fact provenance.
        """
        run_id = run_id or _new_id("run")

        run_metadata = dict(metadata or {})
        if document_id is not None:
            run_metadata.setdefault("document_id", document_id)

        self.connection.execute(
            """
            INSERT INTO processing_runs (run_id, created_at, metadata_json)
            VALUES (?, ?, ?)
            """,
            (run_id, _now(), _json(run_metadata) if run_metadata else None),
        )
        self.connection.commit()

        return run_id

    def save_results(
        self,
        results: Iterable[Any],
        *,
        run_id: str,
        document_id: Optional[str] = None,
        chunk_id: Optional[str] = None,
    ) -> list[str]:
        """
        Persist multiple ReaderResults in one transaction.

        Returns the generated fact IDs in the same order as the results.
        """
        fact_ids = []

        with self.transaction():
            for result in results:
                fact_ids.append(
                    self._save_result(
                        result,
                        run_id=run_id,
                        document_id=document_id,
                        chunk_id=chunk_id,
                    )
                )

        return fact_ids

    def save_result(
        self,
        result: Any,
        *,
        run_id: str,
        document_id: Optional[str] = None,
        chunk_id: Optional[str] = None,
    ) -> str:
        """Persist one complete ReaderResult atomically."""
        with self.transaction():
            return self._save_result(
                result,
                run_id=run_id,
                document_id=document_id,
                chunk_id=chunk_id,
            )

    def _save_result(
        self,
        result: Any,
        *,
        run_id: str,
        document_id: Optional[str],
        chunk_id: Optional[str],
    ) -> str:
        now = _now()
        fact_id = _new_id("fact")

        question = _text(_get(result, "question", "")) or ""
        fact_type = _text(_get(result, "fact_type", "unknown")) or "unknown"
        status = _text(_get(result, "status", "UNKNOWN")) or "UNKNOWN"
        reason = _text(_get(result, "reason"))

        # Make sure the supplied run actually exists.
        run_exists = self.connection.execute(
            "SELECT 1 FROM processing_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()

        if run_exists is None:
            raise ValueError(
                f"Unknown run_id {run_id!r}. Call start_run() first."
            )

        self.connection.execute(
            """
            INSERT INTO facts (
                fact_id,
                run_id,
                document_id,
                chunk_id,
                question,
                fact_type,
                status,
                reason,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact_id,
                run_id,
                document_id,
                chunk_id,
                question,
                fact_type,
                status,
                reason,
                now,
            ),
        )

        # Keep the exact ReaderResult snapshot as an escape hatch. The
        # normalized tables are canonical for querying; this preserves fields
        # if ReaderResult grows before the schema is updated.
        result_id = _new_id("result")

        self.connection.execute(
            """
            INSERT INTO reader_results (
                result_id,
                fact_id,
                raw_json,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                result_id,
                fact_id,
                _json(result),
                now,
            ),
        )

        initial_claim = _get(result, "initial_claim")
        if initial_claim is not None:
            initial_claim_id = self._insert_claim(
                fact_id=fact_id,
                claim=initial_claim,
                role="INITIAL",
                created_at=now,
            )

            self._insert_claim_evidence(
                fact_id=fact_id,
                claim_id=initial_claim_id,
                claim=initial_claim,
                evidence_role="INITIAL",
                created_at=now,
            )

        evidence_repair = _get(result, "evidence_repair")
        if evidence_repair is not None:
            self._insert_evidence(
                fact_id=fact_id,
                claim_id=None,
                evidence=evidence_repair,
                evidence_role="EVIDENCE_REPAIR",
                created_at=now,
            )

        support_judgment = _get(result, "support_judgment")
        if support_judgment is not None:
            self._insert_support_judgment(
                fact_id=fact_id,
                judgment=support_judgment,
                created_at=now,
            )

        corrected_claim = _get(result, "corrected_claim")
        if corrected_claim is not None:
            corrected_claim_id = self._insert_claim(
                fact_id=fact_id,
                claim=corrected_claim,
                role="CORRECTED",
                created_at=now,
            )

            self._insert_claim_evidence(
                fact_id=fact_id,
                claim_id=corrected_claim_id,
                claim=corrected_claim,
                evidence_role="CORRECTED",
                created_at=now,
            )

        revision = _get(result, "revision")
        if revision is not None:
            self._insert_revision(
                fact_id=fact_id,
                revision=revision,
                created_at=now,
            )

        return fact_id

    def _insert_claim(
        self,
        *,
        fact_id: str,
        claim: Any,
        role: str,
        created_at: str,
    ) -> str:
        claim_id = _new_id("claim")
        value = _text(_get(claim, "value"))

        self.connection.execute(
            """
            INSERT INTO claims (
                claim_id,
                fact_id,
                claim_role,
                value,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (claim_id, fact_id, role, value, created_at),
        )

        return claim_id

    def _insert_claim_evidence(
        self,
        *,
        fact_id: str,
        claim_id: str,
        claim: Any,
        evidence_role: str,
        created_at: str,
    ) -> Optional[str]:
        evidence = _get(claim, "evidence")
        if evidence is None:
            return None

        return self._insert_evidence(
            fact_id=fact_id,
            claim_id=claim_id,
            evidence=evidence,
            evidence_role=evidence_role,
            created_at=created_at,
        )

    def _insert_evidence(
        self,
        *,
        fact_id: str,
        claim_id: Optional[str],
        evidence: Any,
        evidence_role: str,
        created_at: str,
    ) -> Optional[str]:
        quote = _text(_get(evidence, "quote"))
        if quote is None:
            return None

        evidence_id = _new_id("evidence")

        self.connection.execute(
            """
            INSERT INTO evidence (
                evidence_id,
                fact_id,
                claim_id,
                evidence_role,
                quote,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                fact_id,
                claim_id,
                evidence_role,
                quote,
                created_at,
            ),
        )

        return evidence_id

    def _insert_support_judgment(
        self,
        *,
        fact_id: str,
        judgment: Any,
        created_at: str,
    ) -> None:
        # SupportJudgment may be a string, enum, dataclass, or another domain
        # object. Keep both a readable judgment and the complete raw object.
        judgment_text = _text(judgment)

        self.connection.execute(
            """
            INSERT INTO support_judgments (
                support_judgment_id,
                fact_id,
                judgment,
                raw_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                _new_id("support"),
                fact_id,
                judgment_text,
                _json(judgment),
                created_at,
            ),
        )

    def _insert_revision(
        self,
        *,
        fact_id: str,
        revision: Any,
        created_at: str,
    ) -> None:
        evidence = _get(revision, "evidence")
        evidence_id = self._insert_evidence(
            fact_id=fact_id,
            claim_id=None,
            evidence=evidence,
            evidence_role="REVISION",
            created_at=created_at,
        )

        computed_value = _get(revision, "computed_value")

        # ComputedValue is expected to wrap the actual value. If it is a
        # primitive, _text() still handles it correctly.
        if computed_value is not None:
            computed_value = _get(
                computed_value,
                "value",
                computed_value,
            )

        self.connection.execute(
            """
            INSERT INTO revisions (
                revision_id,
                fact_id,
                evidence_id,
                operation,
                amount,
                computed_value,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _new_id("revision"),
                fact_id,
                evidence_id,
                _text(_get(revision, "operation")),
                _text(_get(revision, "amount")),
                _text(computed_value),
                created_at,
            ),
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_fact(self, fact_id: str) -> Optional[dict[str, Any]]:
        """Return one fact and its complete normalized history."""
        fact = self.connection.execute(
            "SELECT * FROM facts WHERE fact_id = ?",
            (fact_id,),
        ).fetchone()

        if fact is None:
            return None

        result = dict(fact)

        result["claims"] = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT * FROM claims
                WHERE fact_id = ?
                ORDER BY created_at, rowid
                """,
                (fact_id,),
            )
        ]

        result["evidence"] = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT * FROM evidence
                WHERE fact_id = ?
                ORDER BY created_at, rowid
                """,
                (fact_id,),
            )
        ]

        result["support_judgments"] = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT * FROM support_judgments
                WHERE fact_id = ?
                ORDER BY created_at, rowid
                """,
                (fact_id,),
            )
        ]

        result["revisions"] = [
            dict(row)
            for row in self.connection.execute(
                """
                SELECT * FROM revisions
                WHERE fact_id = ?
                ORDER BY created_at, rowid
                """,
                (fact_id,),
            )
        ]

        return result

    def list_facts(
        self,
        *,
        document_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """List canonical fact records, newest first."""
        clauses = []
        params = []

        if document_id is not None:
            clauses.append("document_id = ?")
            params.append(document_id)

        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = self.connection.execute(
            f"""
            SELECT *
            FROM facts
            {where}
            ORDER BY created_at DESC
            """,
            params,
        ).fetchall()

        return [dict(row) for row in rows]


if __name__ == "__main__":
    print(
        "ReaderResultStore is a library module. "
        "Import it from your Reader pipeline rather than running it directly."
    )
