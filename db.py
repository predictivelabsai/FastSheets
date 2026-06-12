"""FastSheets data layer — SQLite sheets + cells."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = os.getenv("FASTSHEETS_DB") or str(Path(__file__).parent / "fastsheets.sqlite")


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
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
    fmt           TEXT,                 -- space-separated: currency|percent|comma + bold
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
        # migrate older DBs that predate the fmt column
        have = {r[1] for r in conn.execute("PRAGMA table_info(cells)").fetchall()}
        if "fmt" not in have:
            conn.execute("ALTER TABLE cells ADD COLUMN fmt TEXT")


def sheets():
    return rows("""SELECT s.*, (SELECT COUNT(*) FROM cells c WHERE c.sheet_id=s.id AND c.raw IS NOT NULL AND c.raw!='') n
                   FROM sheets s ORDER BY s.id""")


def sheet(sid):
    return one("SELECT * FROM sheets WHERE id=?", (sid,))


def cells(sid) -> dict:
    out = {}
    for r in rows("SELECT row, col, raw FROM cells WHERE sheet_id=? AND raw IS NOT NULL AND raw!=''", (sid,)):
        out[(r["row"], r["col"])] = r["raw"]
    return out


def formats(sid) -> dict:
    out = {}
    for r in rows("SELECT row, col, fmt FROM cells WHERE sheet_id=? AND fmt IS NOT NULL AND fmt!=''", (sid,)):
        out[(r["row"], r["col"])] = r["fmt"]
    return out


def get_cell(sid, row, col):
    return one("SELECT raw, fmt FROM cells WHERE sheet_id=? AND row=? AND col=?", (sid, row, col))


def set_cell(sid, row, col, raw):
    """Set a cell's raw value, preserving any existing format. A row that ends
    up with neither a value nor a format is removed."""
    with cursor() as conn:
        if raw is None or raw == "":
            # keep the row only if it still carries a format
            conn.execute(
                "UPDATE cells SET raw=NULL WHERE sheet_id=? AND row=? AND col=?", (sid, row, col))
            conn.execute(
                "DELETE FROM cells WHERE sheet_id=? AND row=? AND col=? AND (fmt IS NULL OR fmt='')",
                (sid, row, col))
        else:
            conn.execute("""INSERT INTO cells(sheet_id,row,col,raw) VALUES (?,?,?,?)
                            ON CONFLICT(sheet_id,row,col) DO UPDATE SET raw=excluded.raw""",
                         (sid, row, col, raw))


NUMBER_FORMATS = ("currency", "percent", "comma")


def toggle_format(sid, row, col, token) -> bool:
    """Toggle a format token on a cell. Number-style tokens are mutually
    exclusive; 'bold' is independent. Empty/None clears all formatting."""
    cur = get_cell(sid, row, col)
    fmt = set((cur["fmt"] or "").split()) if cur and cur["fmt"] else set()
    if token == "clear" or token is None:
        fmt = set()
    elif token == "bold":
        fmt ^= {"bold"}
    elif token in NUMBER_FORMATS:
        had = token in fmt
        fmt -= set(NUMBER_FORMATS)
        if not had:
            fmt.add(token)
    else:
        return False
    new = " ".join(sorted(fmt))
    with cursor() as conn:
        if not new and not (cur and cur["raw"]):
            conn.execute("DELETE FROM cells WHERE sheet_id=? AND row=? AND col=?", (sid, row, col))
        else:
            conn.execute("""INSERT INTO cells(sheet_id,row,col,fmt) VALUES (?,?,?,?)
                            ON CONFLICT(sheet_id,row,col) DO UPDATE SET fmt=excluded.fmt""",
                         (sid, row, col, new or None))
    return True


def fill(sid, row, col, direction) -> int:
    """Copy the selected cell (value + format) across the rest of its row/column,
    shifting relative cell references in formulas. Returns the number of cells
    written. direction: 'down' | 'right'."""
    import engine
    src = get_cell(sid, row, col)
    if not src or (not src["raw"] and not src["fmt"]):
        return 0
    s = sheet(sid)
    raw, fmt = src["raw"], src["fmt"]
    n = 0
    with cursor() as conn:
        if direction == "down":
            targets = [(r, col, r - row, 0) for r in range(row + 1, s["n_rows"])]
        else:
            targets = [(row, c, 0, c - col) for c in range(col + 1, s["n_cols"])]
        for (tr, tc, drow, dcol) in targets:
            new_raw = engine.shift_formula(raw, drow, dcol) if raw else None
            conn.execute("""INSERT INTO cells(sheet_id,row,col,raw,fmt) VALUES (?,?,?,?,?)
                            ON CONFLICT(sheet_id,row,col) DO UPDATE SET raw=excluded.raw, fmt=excluded.fmt""",
                         (sid, tr, tc, new_raw, fmt))
            n += 1
    return n


def create_sheet(title, n_rows=20, n_cols=8, cell_map=None):
    with cursor() as conn:
        conn.execute("INSERT INTO sheets(title,n_rows,n_cols,created) VALUES (?,?,?,datetime('now'))",
                     (title, n_rows, n_cols))
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        if cell_map:
            for (r, c), raw in cell_map.items():
                conn.execute("INSERT INTO cells(sheet_id,row,col,raw) VALUES (?,?,?,?)", (sid, r, c, raw))
    return sid


def grow_sheet(sid: int, add_rows: int = 0, add_cols: int = 0):
    with cursor() as conn:
        conn.execute("UPDATE sheets SET n_rows = MIN(100, n_rows + ?), n_cols = MIN(26, n_cols + ?) WHERE id=?",
                     (max(0, add_rows), max(0, add_cols), sid))
