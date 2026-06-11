# Skills

Capability reference for FastSheets + the shared **Frappe → FastHTML migration
playbook** (same recipe across `fasthtml-oss-migrations`; see `FastCRM/SKILLS.md`).

---

## Part 1 — FastSheets capabilities

**Entry:** `python web_app.py` → http://localhost:5014
(login `admin@fastsheets.example` / `FastSheets2026$`).

### Pages

| View | Route | What it shows |
|---|---|---|
| Sheets | `/` | your spreadsheets |
| Grid | `/sheet/{id}?sel=r_c` | grid + formula bar; click a cell to select |
| New | `/new` | create a blank sheet |
| AI Assistant | `/ai` | data/formula chat (right rail) |

### Formula engine (`engine.py`)

`Sheet(raw_map)` evaluates cells on demand with memoisation + recursion guard.
Supports `SUM/AVERAGE/MIN/MAX/COUNT/PRODUCT(range)`, cell refs, ranges,
arithmetic (`+-*/%`), percentages. Arithmetic uses a restricted `ast` walker
(`_safe_eval`) — never Python `eval`. `#CIRC` for cycles, `#ERR` for bad input.
Helpers: `col_to_num`, `num_to_col`, `parse_ref`.

### Editing

The formula bar posts `(row, col, raw)` to `/sheet/{id}/cell`; `db.set_cell`
upserts/deletes the cell and the grid re-renders, recomputing all dependents.

### AI (`web/ai.py`)

`snapshot()` renders each sheet as `ref=value [formula]` lines so the model sees
both computed results and formulas — it can explain and suggest formulas.

---

## Part 2 — Frappe → FastHTML migration playbook

1. **Mine the schema** — `python scripts/frappe_doctype_to_schema.py /tmp/frappe-sheets`.
2. **Identify the un-portable core** — Sheets' value is *real-time collab*
   (`Sheet Collab State`/`Op Log`/`Seq`). Plain HTMX can't do multi-cursor OT, so
   scope to **single-user** and build the formula engine instead (the part that's
   a great server-side fit). Be explicit about the cut in `docs/ROADMAP.md`.
3. **FastHTML shell** — `fast_app(pico=False, hdrs=[Style(CSS)])`; `page()` wrapper.
4. **HTMX/no-JS editing** — a formula bar + selected-cell `?sel=` query gives a
   spreadsheet UX with **zero** client JS for editing; cells are plain links.
5. **Safety first** — user-entered formulas are untrusted input: parse with `ast`
   and walk a whitelist of nodes; never `eval`. Reusable pattern for any
   expression feature.
6. **LLM grounding** — serialise computed state (value + formula) so the model
   reasons over results, not just raw cells.
7. **Capture the demo** — Playwright MCP → frames → `build_demo_gif.sh`.
8. **Ship deploy paths** — `.env.sample`, `Dockerfile`, `docker-compose.yml`.

### Reusable assets

| File | Reuse |
|---|---|
| `engine.py` | safe spreadsheet/expression evaluator (refs, ranges, AST arithmetic) |
| `scripts/frappe_doctype_to_schema.py` | DocType JSON → SQLite DDL |
| `scripts/build_demo_gif.sh` | frames → demo GIF |
| `web/layout.py` | 3-pane shell + CSS tokens + SSE chat JS |
