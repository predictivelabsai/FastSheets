# FastSheets Roadmap — Frappe Sheets feature comparison

FastSheets ports the core of [Frappe Sheets](https://github.com/frappe/sheets)
(6 doctypes: `Sheet`, `Sheet Cell`, `Sheet Collab State`, `Sheet Op Log`,
`Sheet Seq`, `Sheet Snapshot`) to a FastHTML demonstrator — single-user, with a
real formula engine.

## Implemented ✅

| Capability | Upstream doctype(s) | FastSheets |
|---|---|---|
| Sheets | `Sheet` | `sheets` |
| Cells | `Sheet Cell` | `cells` (raw value/formula) |
| Editing | op log / collab | formula bar → `set_cell` → recompute |
| **Formula engine** | client-side | `engine.py` (safe, no `eval`) |
| Functions | — | SUM/AVERAGE/MIN/MAX/COUNT/PRODUCT |
| Refs & arithmetic | — | A1, ranges, `+-*/`, `%`, circular-safe |
| **Cell formatting** | style on `Sheet Cell` | currency / percent / thousands + bold (`cells.fmt`) |
| **Fill down / right** | drag-fill | copy value+format, shifting relative refs |
| **AI assistant** | *(not upstream)* | grounded in computed values + formulas |

## Near-term roadmap 🔜

1. ✅ **More functions** (done) — IF, ROUND, ABS, SQRT, INT, scalar MIN/MAX, comparisons (CONCAT/VLOOKUP/dates still to come).
2. ✅ **Cell formatting** (done) — currency / percent / thousands number formats
   and bold, toggled from a toolbar and stored on `cells.fmt`; colours still to come.
3. ✅ **Grow the grid** (done) — add rows/columns; insert/delete rows still to come.
4. ✅ **Fill down / right** (done) — copies the selected cell's value *and* format
   across its column/row, shifting relative cell references in formulas
   (`engine.shift_formula`). Drag-to-fill and paste-from-clipboard still to come.
5. **Charts** — render a chart from a range (reuse FastInsights' Plotly helper).
6. **Snapshots / undo** — `Sheet Snapshot` + an op log for undo/redo.

## Later / out-of-scope 🗓️

- **Real-time collaborative editing** — `Sheet Collab State` / `Sheet Op Log` /
  `Sheet Seq` implement multi-user OT (operational transform). That live
  multi-cursor collaboration is the one thing plain HTMX can't do; it needs a
  WebSocket + OT/CRDT layer. FastSheets is **single-user** by design.
- **Import/export** — XLSX/CSV round-trip.
- **Named ranges**, cross-sheet references, pivot tables.

## Design notes

The interesting part is `engine.py`: a **safe** evaluator that resolves refs and
ranges, substitutes function results, and evaluates the remaining arithmetic with
a restricted `ast` walker (never `eval`), with recursion-guarded circular-ref
detection. Editing posts a single cell and re-renders the grid, so all dependent
formulas recompute. The deliberate gap vs upstream is **real-time collab** (the
five collab-related doctypes) — out of scope for a server-rendered single-user demo.
