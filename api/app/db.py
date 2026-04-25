"""psycopg3 connection pool — one shared pool per process."""

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

_pool: ConnectionPool | None = None


def init_pool() -> None:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            settings().dsn,
            min_size=1,
            max_size=8,
            kwargs={"row_factory": dict_row, "autocommit": True},
            open=True,
        )


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def conn() -> Iterator[psycopg.Connection]:
    if _pool is None:
        init_pool()
    assert _pool is not None
    with _pool.connection() as c:
        yield c


def fetch_all(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def fetch_one(sql: str, params: tuple | dict | None = None) -> dict | None:
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()
        return row


def execute(sql: str, params: tuple | dict | None = None) -> None:
    with conn() as c, c.cursor() as cur:
        cur.execute(sql, params or ())
