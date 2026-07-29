"""FastSheets public reads and token-gated integration writes."""

import db

from .api_core import Resource, SQLiteBackend, create_sqlite_api

RESOURCES = (
    Resource("workbooks", "sheets", "Workbooks", "Spreadsheet workbooks and their dimensions.", write_fields=("title", "n_rows", "n_cols"), search_fields=("title",)),
    Resource("cells", "cells", "Cells", "Raw values, formulas, and formatting for workbook cells.", search_fields=("raw", "fmt"), primary_key="sheet_id"),
)

backend = SQLiteBackend(db.DB_PATH, RESOURCES, initialize=db.init_schema)
api = create_sqlite_api(
    product="FastSheets", version="1.0.0",
    description="Open integration access to FastSheets workbooks and cells.",
    base_url="https://sheets.fastsme.com", backend=backend, resources=RESOURCES,
)
