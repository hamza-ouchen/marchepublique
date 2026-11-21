"""Contrat SQL : paramètres liés, champs autorisés et rollback sur journal KO."""

from contextlib import contextmanager

import psycopg
import pytest

from sou9na_rag.postgres import CpsRepository, CpsSession
from sou9na_rag.store import BackendError


class Cursor:
    rowcount = 1


class Connection:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return Cursor()


def test_only_document_state_and_run_log_are_written():
    connection = Connection()
    CpsSession(connection, 42).finish("ready", None, "run-test", 123)
    sql, params = connection.calls[0]
    assert "SET statut = %s, echec_raison = %s, updated_at" in sql
    assert params == ("ready", None, 42)
    assert "INSERT INTO public.run_logs" in connection.calls[1][0]
    assert "tokens" in connection.calls[1][0]


def test_conflicting_status_prevents_logging():
    connection = Connection()
    original = connection.execute

    def conflict(*args):
        cursor = original(*args)
        cursor.rowcount = 0
        return cursor

    connection.execute = conflict
    with pytest.raises(BackendError, match="CPS_STATUS_CONFLICT"):
        CpsSession(connection, 42).finish("ready", None, "run-test", 0)
    assert len(connection.calls) == 1


def test_transaction_error_is_sanitized_and_context_rolls_back(monkeypatch):
    repo = CpsRepository("not-a-real-dsn")
    state = []

    @contextmanager
    def connect():
        try:
            yield Connection()
        except Exception:
            state.append("rollback")
            raise

    monkeypatch.setattr(repo, "connect", connect)
    with pytest.raises(BackendError, match="SUPABASE_TRANSACTION_FAILED") as error:
        with repo.session(42):
            raise psycopg.OperationalError("secret-dsn")
    assert state == ["rollback"] and "secret" not in str(error.value)


def test_document_id_cannot_be_sql_fragment():
    with pytest.raises(BackendError, match="INVALID_DOCUMENT_ID"):
        with CpsRepository("fake").session("1; DROP TABLE tenders"):
            pytest.fail("SQL must not execute")
