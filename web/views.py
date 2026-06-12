"""Center-pane renderers for FastSheets."""
from __future__ import annotations

from fasthtml.common import (
    Div, H1, H3, P, Span, A, Table, Thead, Tbody, Tr, Th, Td, Form, Input, Button, NotStr,
)

import db
import engine


def _title(title, sub="", *actions):
    return Div(Div(H1(title), P(sub, cls="sub") if sub else None),
               Div(*actions) if actions else None, cls="page-title")


def sheets_list():
    sheets = db.sheets()
    cards = [A(H3(s["title"]),
               Div(f"{s['n_rows']}×{s['n_cols']} grid · {s['n']} filled cells", cls="meta"),
               href=f"/sheet/{s['id']}", cls="sheet-card") for s in sheets]
    return (_title("Sheets", f"{len(sheets)} spreadsheets", A("＋ New sheet", href="/new", cls="btn primary")),
            Div(*cards) if cards else Div(P("No sheets yet."), style="color:var(--text-mute);padding:40px;"))


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def sheet_view(sid, sel=None):
    s = db.sheet(sid)
    if not s:
        return _title("Sheet not found"), P("No such sheet.")
    raw = db.cells(sid)
    fmts = db.formats(sid)
    sheet = engine.Sheet(raw)
    nrows, ncols = s["n_rows"], s["n_cols"]

    sel_rc = None
    if sel and "_" in sel:
        try:
            sel_rc = tuple(int(x) for x in sel.split("_"))
        except ValueError:
            sel_rc = None
    sel_ref = (engine.num_to_col(sel_rc[1]) + str(sel_rc[0] + 1)) if sel_rc else "A1"
    sel_raw = raw.get(sel_rc, "") if sel_rc else ""
    sel_fmt = fmts.get(sel_rc, "") if sel_rc else ""

    # header row
    head = Tr(Th("", cls="rowhead"), *[Th(engine.num_to_col(c)) for c in range(ncols)])
    body = []
    for r in range(nrows):
        tds = [Td(str(r + 1), cls="rowhead")]
        for c in range(ncols):
            val = sheet.value(r, c)
            fmt = fmts.get((r, c), "")
            formatted = engine.format_value(val, fmt)
            disp = formatted if formatted is not None else sheet.display(r, c)
            is_formula = (raw.get((r, c), "") or "").startswith("=")
            classes = []
            if _is_num(val):
                classes.append("num")
            if is_formula:
                classes.append("formula")
            if "bold" in fmt:
                classes.append("bold")
            if sel_rc == (r, c):
                classes.append("sel")
            tds.append(Td(A(disp, href=f"/sheet/{sid}?sel={r}_{c}"), cls=" ".join(classes)))
        body.append(Tr(*tds))
    grid = Div(Table(Thead(head), Tbody(*body), cls="grid"), cls="grid-wrap")

    fbar = Div(
        Span(sel_ref, cls="cellref"),
        Form(Input(name="raw", value=sel_raw, id="fbar-input", autocomplete="off",
                   placeholder="Enter a value or =SUM(A1:A3)"),
             Input(type="hidden", name="row", value=str(sel_rc[0] if sel_rc else 0)),
             Input(type="hidden", name="col", value=str(sel_rc[1] if sel_rc else 0)),
             Button("Set", cls="btn primary", type="submit"),
             method="post", action=f"/sheet/{sid}/cell"),
        cls="fbar")

    fmt_bar = _format_bar(sid, sel_rc, sel_fmt)

    grow = Div(
        Form(Input(type="hidden", name="add_rows", value="5"),
             Button("＋ 5 rows", cls="btn", type="submit"), method="post", action=f"/sheet/{sid}/grow", style="display:inline;"),
        Form(Input(type="hidden", name="add_cols", value="2"),
             Button("＋ 2 cols", cls="btn", type="submit"), method="post", action=f"/sheet/{sid}/grow", style="display:inline;"),
        cls="grow-bar", style="display:flex;gap:8px;margin-top:10px;")
    return (_title(s["title"], f"{nrows}×{ncols}", A("← All sheets", href="/", cls="btn")),
            fbar, fmt_bar, grid, grow,
            P(NotStr("Click a cell to select it, then edit in the bar above. Formulas start with "
                     "<code>=</code> — try <code>=SUM(B2:B6)</code>, <code>=AVERAGE(A1:A3)</code>, "
                     "<code>=IF(A1&gt;100, A1*0.9, A1)</code>, <code>=ROUND(B2/C2, 2)</code>, "
                     "<code>=ABS(A1-B1)</code>, <code>=D2*8%</code>. Format a cell or fill it "
                     "down/right with the toolbar; formulas shift their references as they fill."),
              cls="hint"))


def _format_bar(sid, sel_rc, sel_fmt):
    """Formatting + fill toolbar that acts on the selected cell."""
    if not sel_rc:
        return Div(Span("Select a cell to format or fill.", cls="sub"),
                   cls="fmt-bar", style="color:var(--text-mute);")
    r, c = sel_rc
    toks = set((sel_fmt or "").split())

    def fbtn(label, token, title, active=False):
        return Form(
            Input(type="hidden", name="row", value=str(r)),
            Input(type="hidden", name="col", value=str(c)),
            Input(type="hidden", name="token", value=token),
            Button(label, cls="btn sm" + (" primary" if active else ""), type="submit", title=title),
            method="post", action=f"/sheet/{sid}/format", style="display:inline;")

    def fillbtn(label, direction, title):
        return Form(
            Input(type="hidden", name="row", value=str(r)),
            Input(type="hidden", name="col", value=str(c)),
            Input(type="hidden", name="dir", value=direction),
            Button(label, cls="btn sm", type="submit", title=title),
            method="post", action=f"/sheet/{sid}/fill", style="display:inline;")

    return Div(
        Span("Format:", cls="fmt-label"),
        fbtn(NotStr("<b>B</b>"), "bold", "Bold", "bold" in toks),
        fbtn("£", "currency", "Currency", "currency" in toks),
        fbtn("%", "percent", "Percent", "percent" in toks),
        fbtn("1,000", "comma", "Thousands separator", "comma" in toks),
        fbtn("Clear", "clear", "Clear formatting"),
        Span("Fill:", cls="fmt-label", style="margin-left:10px;"),
        fillbtn("↓ Down", "down", "Fill down the column"),
        fillbtn("→ Right", "right", "Fill across the row"),
        cls="fmt-bar")


def new_sheet_view():
    return (_title("New sheet", "Create a blank spreadsheet."),
            Div(Form(
                Span("Sheet name", style="font-weight:600;"),
                Input(name="title", placeholder="e.g. Expenses", required=True),
                Div(Button("Create", cls="btn primary", type="submit"),
                    A("Cancel", href="/", cls="btn"), style="margin-top:12px;display:flex;gap:8px;"),
                method="post", action="/new"), cls="gen-card"))
