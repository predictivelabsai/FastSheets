"""FastSheets — an open-source spreadsheet built with FastHTML.

A server-side, HTMX-driven port of the core of Frappe Sheets: editable grids
with a real formula engine (SUM/AVERAGE/MIN/MAX/refs/arithmetic), multiple
sheets, and an AI assistant grounded in the computed values.

Run:
    python web_app.py            # http://localhost:5014

Login: admin@fastsheets.example / FastSheets2026$  (override via .env)
"""
from __future__ import annotations

import os
import json
import secrets
import uuid
import logging

from dotenv import load_dotenv
load_dotenv()

from fasthtml.common import (
    fast_app, serve, Div, H1, P, A, Form, Input, Button, NotStr,
    RedirectResponse, Script, Style, Link, Title,
)
from starlette.responses import StreamingResponse, Response

import db
from web.layout import page, LAYOUT_CSS
from web import views, ai

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("fastsheets")

VALID_EMAIL = os.getenv("FASTSHEETS_ADMIN_EMAIL", "admin@fastsheets.example")
VALID_PASSWORD = os.getenv("FASTSHEETS_ADMIN_PASSWORD", "FastSheets2026$")
ENV_LABEL = os.getenv("FASTSHEETS_ENV_LABEL", "FastSheets")
SECRET = os.getenv("FASTSHEETS_SECRET", secrets.token_hex(32))
PORT = int(os.getenv("FASTSHEETS_PORT", "5014"))

app, rt = fast_app(live=False, pico=False, secret_key=SECRET, hdrs=[Style(LAYOUT_CSS)])


def _user(session):
    return session.get("user")


def _thread(session):
    if "thread" not in session:
        session["thread"] = uuid.uuid4().hex
    return session["thread"]


def _guard(session, active, builder):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    content = builder() if callable(builder) else builder
    if not isinstance(content, tuple):
        content = (content,)
    return page(active, ENV_LABEL, _user(session), _thread(session), db.sheets(), *content)


def _login_card(error="", email=""):
    return Title("FastSheets — Sign in"), Style(LAYOUT_CSS), Div(
        Form(H1("FastSheets"), P("Sign in to your spreadsheets"),
             Input(name="email", type="email", placeholder="Email", value=email, required=True),
             Input(name="password", type="password", placeholder="Password", required=True),
             P(error, cls="error") if error else None,
             Button("Sign in", cls="btn primary", type="submit"),
             P(NotStr("Demo: <code>admin@fastsheets.example</code> / <code>FastSheets2026$</code>"), cls="hint"),
             method="post", action="/login", cls="login-card"), cls="login-wrap")


@rt("/login")
def get(session):
    if _user(session):
        return RedirectResponse("/", status_code=303)
    return _login_card()


@rt("/login")
def post(session, email: str = "", password: str = ""):
    if email.strip().lower() == VALID_EMAIL.lower() and password == VALID_PASSWORD:
        session["user"] = email.strip().lower()
        return RedirectResponse("/", status_code=303)
    return _login_card("Invalid email or password.", email)


@rt("/logout")
def get(session):
    session.pop("user", None)
    return RedirectResponse("/login", status_code=303)


@rt("/")
def get(session):
    return _guard(session, "sheets", views.sheets_list)


@rt("/sheet/{sid}")
def get(session, sid: int, sel: str = ""):
    return _guard(session, "sheets", lambda: views.sheet_view(sid, sel))


@rt("/sheet/{sid}/cell")
def post(session, sid: int, row: int = 0, col: int = 0, raw: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    db.set_cell(sid, row, col, raw.strip())
    return RedirectResponse(f"/sheet/{sid}?sel={row}_{col}", status_code=303)


@rt("/sheet/{sid}/format")
def post(session, sid: int, row: int = 0, col: int = 0, token: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    db.toggle_format(sid, row, col, token)
    return RedirectResponse(f"/sheet/{sid}?sel={row}_{col}", status_code=303)


@rt("/sheet/{sid}/fill")
def post(session, sid: int, row: int = 0, col: int = 0, dir: str = "down"):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    db.fill(sid, row, col, dir if dir in ("down", "right") else "down")
    return RedirectResponse(f"/sheet/{sid}?sel={row}_{col}", status_code=303)


@rt("/sheet/{sid}/grow")
def post(session, sid: int, add_rows: int = 0, add_cols: int = 0):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    db.grow_sheet(sid, add_rows, add_cols)
    return RedirectResponse(f"/sheet/{sid}", status_code=303)


@rt("/new")
def get(session):
    return _guard(session, "sheets", views.new_sheet_view)


@rt("/new")
def post(session, title: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    title = (title or "Untitled").strip() or "Untitled"
    sid = db.create_sheet(title, 20, 8, {(0, 0): title})
    return RedirectResponse(f"/sheet/{sid}?sel=0_0", status_code=303)


@rt("/ai")
def get(session):
    body = (views._title("AI Assistant", "Chat lives in the right rail. Ask about your data or formulas."),
            Div(NotStr(
                "<div class='gen-card'><h3>What you can ask</h3><ul style='line-height:1.8;'>"
                "<li>“What's the Q1 budget total?”</li><li>“Explain the formula in E7.”</li>"
                "<li>“Which rep sold the most, and how much commission?”</li>"
                "<li>“What formula would average B2:B6?”</li></ul>"
                "<p style='color:var(--text-mute)'>The assistant sees every cell's computed value and formula. "
                "Slash-command (no key): <code>/sheets</code>.</p></div>")))
    return _guard(session, "ai", body)


@rt("/guide")
def get(session):
    body = (views._title("User Guide", "How to drive FastSheets"), Div(NotStr("""
<div class='gen-card'><h3>Sheets</h3><p>Your spreadsheets in the sidebar and on the home page. Open one to edit.</p></div>
<div class='gen-card' style='margin-top:14px;'><h3>Editing</h3><p>Click a cell to select it, then type in the formula bar
and press Set. Formulas start with <code>=</code>:</p>
<ul><li><code>=SUM(B2:B6)</code>, <code>=AVERAGE(A1:A3)</code>, <code>=MIN/MAX/COUNT/PRODUCT(range)</code></li>
<li>arithmetic with refs: <code>=A1*C1+5</code>, <code>=D2*8%</code></li></ul>
<p>Formula cells show in green; numbers are right-aligned. Circular references show <code>#CIRC</code>.</p></div>
<div class='gen-card' style='margin-top:14px;'><h3>AI Assistant</h3><p>The right rail sees every computed value and formula,
so it can explain results and suggest formulas. Set <code>MODEL_PROVIDER</code> + a key in <code>.env</code>.</p></div>
""")))
    return _guard(session, "guide", body)


@rt("/chat/new")
def get(session):
    session["thread"] = uuid.uuid4().hex
    return P("Ask about your sheets, totals or formulas — or use /sheets /help.", cls="chat-empty-hint")


@rt("/chat/stream")
async def post(session, message: str = "", thread_id: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    message = (message or "").strip()
    if not message:
        return Response("No message", status_code=400)
    tid = thread_id or _thread(session)

    async def gen():
        with db.cursor() as conn:
            conn.execute("INSERT INTO chat_messages(thread_id,role,content,created) VALUES(?,?,?,datetime('now'))",
                         (tid, "user", message))
        full = []
        async for chunk in ai.stream_chat(message):
            if chunk.startswith("data: "):
                try:
                    tok = json.loads(chunk[6:]).get("token")
                    if tok:
                        full.append(tok)
                except Exception:
                    pass
            yield chunk
        with db.cursor() as conn:
            conn.execute("INSERT INTO chat_messages(thread_id,role,content,created) VALUES(?,?,?,datetime('now'))",
                         (tid, "assistant", "".join(full)))

    return StreamingResponse(gen(), media_type="text/event-stream")


def _ensure_db():
    if not db.db_exists():
        logger.info("No database found — seeding sample sheets…")
        import seed
        seed.build()
    else:
        db.init_schema()  # idempotent; also runs the fmt-column migration


_ensure_db()

if __name__ == "__main__":
    logger.info("FastSheets on http://localhost:%s  (login %s)", PORT, VALID_EMAIL)
    serve(port=PORT, reload=os.getenv("FASTSHEETS_RELOAD", "0") == "1")
