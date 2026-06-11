"""FastSheets data layer — SQLite sheets + cells."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = os.getenv("FASTSHEETS_DB") or str(Path(__file__).parent / "fastsheets.sqlite")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def cursor():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def db_exists() -> bool:
    p = Path(DB_PATH)
    return p.exists() and p.stat().st_size > 0


def rows(sql, params=()):
    with cursor() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(sql, params=()):
    with cursor() as conn:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS sheets (
    id            INTEGER PRIMARY KEY,
    title         TEXT NOT NULL,
    n_rows        INTEGER NOT NULL DEFAULT 20,
    n_cols        INTEGER NOT NULL DEFAULT 8,
    created       TEXT
);
CREATE TABLE IF NOT EXISTS cells (
    sheet_id      INTEGER REFERENCES sheets(id) ON DELETE CASCADE,
    row           INTEGER NOT NULL,
    col           INTEGER NOT NULL,
    raw           TEXT,
    PRIMARY KEY (sheet_id, row, col)
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id            INTEGER PRIMARY KEY,
    thread_id     TEXT NOT NULL,
    role          TEXT NOT NULL,
    content       TEXT NOT NULL,
    created       TEXT NOT NULL
);
"""


def init_schema():
    with cursor() as conn:
        conn.executescript(SCHEMA)


def sheets():
    return rows("""SELECT s.*, (SELECT COUNT(*) FROM cells c WHERE c.sheet_id=s.id AND c.raw IS NOT NULL AND c.raw!='') n
                   FROM sheets s ORDER BY s.id""")


def sheet(sid):
    return one("SELECT * FROM sheets WHERE id=?", (sid,))


def cells(sid) -> dict:
    out = {}
    for r in rows("SELECT row, col, raw FROM cells WHERE sheet_id=?", (sid,)):
        out[(r["row"], r["col"])] = r["raw"]
    return out


def set_cell(sid, row, col, raw):
    with cursor() as conn:
        if raw is None or raw == "":
            conn.execute("DELETE FROM cells WHERE sheet_id=? AND row=? AND col=?", (sid, row, col))
        else:
            conn.execute("""INSERT INTO cells(sheet_id,row,col,raw) VALUES (?,?,?,?)
                            ON CONFLICT(sheet_id,row,col) DO UPDATE SET raw=excluded.raw""",
                         (sid, row, col, raw))


def create_sheet(title, n_rows=20, n_cols=8, cell_map=None):
    with cursor() as conn:
        conn.execute("INSERT INTO sheets(title,n_rows,n_cols,created) VALUES (?,?,?,datetime('now'))",
                     (title, n_rows, n_cols))
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        if cell_map:
            for (r, c), raw in cell_map.items():
                conn.execute("INSERT INTO cells(sheet_id,row,col,raw) VALUES (?,?,?,?)", (sid, r, c, raw))
    return sid
