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
| **AI assistant** | *(not upstream)* | grounded in computed values + formulas |

## Near-term roadmap 🔜

1. **More functions** — `IF`, `ROUND`, `CONCAT`, `VLOOKUP`, date functions.
2. **Cell formatting** — number/currency/percent formats, bold, colours
   (Frappe stores style on `Sheet Cell`).
3. **Add/insert/delete rows & columns**; resize the grid beyond the seeded size.
4. **Copy/paste & fill** — drag-fill a formula down a column (relative refs).
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
