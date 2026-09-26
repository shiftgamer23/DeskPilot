"""Postgres-backed persistence for ticket runs, so history survives restarts/redeploys - a real concern
once this runs on a real host (a respin on idle, or any redeploy, replaces the process and wipes
app/infra/run_store.py's in-memory dict).

Fails open like app/infra/cache.py: if DATABASE_URL is unset or the database is unreachable, every
function becomes a no-op / returns nothing, and the app keeps working exactly as before (in-memory only,
today's local-dev default). This module is never a correctness requirement for triage itself - only for
whether ticket history is still there after a restart.

Scope: only the run's identity, status, and final decision are persisted. The step-by-step reasoning
trace (tool_call/tool_result events) is intentionally NOT persisted here - it's ephemeral, in-memory-only,
already durably captured in full by Langfuse (see app/infra/tracing.py) for anyone who needs the deep
trace after the fact.
"""
import json
import logging
from functools import lru_cache
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from app import config

logger = logging.getLogger(__name__)
_warned = False

_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    subject TEXT,
    body TEXT NOT NULL,
    customer_id TEXT,
    provider TEXT,
    status TEXT NOT NULL,
    result JSONB,
    error TEXT,
    created_at DOUBLE PRECISION NOT NULL
);
"""


def _warn_once(msg: str) -> None:
    global _warned
    if not _warned:
        logger.warning(msg)
        _warned = True


@lru_cache(maxsize=1)
def _ready() -> bool:
    if not config.DATABASE_URL:
        return False
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=5) as conn:
            conn.execute(_DDL)
        return True
    except psycopg.Error as e:
        _warn_once(f"Postgres unavailable ({e}); ticket history will not persist across restarts")
        return False


def insert_run(run_id: str, subject: str | None, body: str, customer_id: str | None, provider: str | None,
                status: str, created_at: float) -> None:
    if not _ready():
        return
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=5) as conn:
            conn.execute(
                "INSERT INTO runs (run_id, subject, body, customer_id, provider, status, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (run_id) DO NOTHING",
                (run_id, subject, body, customer_id, provider, status, created_at),
            )
    except psycopg.Error as e:
        _warn_once(f"Postgres insert failed ({e}); this run will not persist")


def update_run(run_id: str, status: str, result: Optional[dict] = None, error: Optional[str] = None) -> None:
    if not _ready():
        return
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=5) as conn:
            conn.execute(
                "UPDATE runs SET status = %s, result = %s, error = %s WHERE run_id = %s",
                (status, json.dumps(result) if result is not None else None, error, run_id),
            )
    except psycopg.Error as e:
        _warn_once(f"Postgres update failed ({e}); this run's final state will not persist")


def list_runs(limit: int = 200) -> list[dict]:
    if not _ready():
        return []
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=5, row_factory=dict_row) as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT %s", (limit,)
            ).fetchall()
        return list(rows)
    except psycopg.Error as e:
        _warn_once(f"Postgres list failed ({e}); starting with empty history")
        return []
