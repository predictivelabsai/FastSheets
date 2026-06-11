"""Seed FastSheets with sample sheets that show off formulas."""
from __future__ import annotations

import db


def _budget():
    # cols: A=Category B=Jan C=Feb D=Mar E=Q1 Total
    rows = [
        ("Category", "Jan", "Feb", "Mar", "Q1 Total"),
        ("Salaries", "42000", "42000", "43500", "=SUM(B2:D2)"),
        ("Marketing", "8000", "12000", "9500", "=SUM(B3:D3)"),
        ("Software", "3200", "3200", "3400", "=SUM(B4:D4)"),
        ("Travel", "1500", "4200", "2100", "=SUM(B5:D5)"),
        ("Office", "2600", "2600", "2600", "=SUM(B6:D6)"),
        ("Total", "=SUM(B2:B6)", "=SUM(C2:C6)", "=SUM(D2:D6)", "=SUM(E2:E6)"),
        ("", "", "", "", ""),
        ("Avg monthly spend", "=AVERAGE(B7:D7)", "", "", ""),
        ("Marketing % of total", "=E3/E7", "", "", ""),
    ]
    cm = {}
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            if val != "":
                cm[(r, c)] = val
    return cm


def _sales():
    rows = [
        ("Rep", "Units", "Price", "Revenue", "Commission 8%"),
        ("Priya", "120", "45", "=B2*C2", "=D2*8%"),
        ("Tom", "98", "45", "=B3*C3", "=D3*8%"),
        ("Lena", "143", "45", "=B4*C4", "=D4*8%"),
        ("Marco", "77", "45", "=B5*C5", "=D5*8%"),
        ("Aisha", "165", "45", "=B6*C6", "=D6*8%"),
        ("Total", "=SUM(B2:B6)", "", "=SUM(D2:D6)", "=SUM(E2:E6)"),
        ("", "", "", "", ""),
        ("Best rep revenue", "=MAX(D2:D6)", "", "", ""),
        ("Avg units", "=AVERAGE(B2:B6)", "", "", ""),
    ]
    cm = {}
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            if val != "":
                cm[(r, c)] = val
    return cm


def build():
    db.init_schema()
    with db.cursor() as conn:
        conn.execute("DELETE FROM cells")
        conn.execute("DELETE FROM sheets")
        conn.execute("DELETE FROM chat_messages")
    db.create_sheet("Q1 Budget", 12, 6, _budget())
    db.create_sheet("Sales Commission", 12, 6, _sales())
    print(f"FastSheets seeded → {db.DB_PATH}")
    print("  2 sheets")


if __name__ == "__main__":
    build()
