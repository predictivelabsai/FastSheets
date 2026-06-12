"""FastSheets formula engine — a small, safe spreadsheet evaluator.

Supports: numeric & text literals, cell refs (A1), ranges in functions
(SUM/AVERAGE/MIN/MAX/COUNT/PRODUCT over A1:B3), and arithmetic with +-*/(),
percentages. Arithmetic is evaluated via a restricted AST walker (no `eval`),
and circular references are detected and reported as #CIRC.
"""
from __future__ import annotations

import ast
import operator
import re

COL_RE = re.compile(r"^([A-Z]+)(\d+)$")
REF_RE = re.compile(r"\b([A-Z]+)(\d+)\b")
RANGE_RE = re.compile(r"\b([A-Z]+\d+):([A-Z]+\d+)\b")
FUNC_RE = re.compile(r"\b(SUM|AVERAGE|AVG|MIN|MAX|COUNT|PRODUCT)\s*\(([^()]*)\)", re.IGNORECASE)

_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}


def col_to_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def num_to_col(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def parse_ref(ref: str):
    m = COL_RE.match(ref)
    if not m:
        return None
    return int(m.group(2)) - 1, col_to_num(m.group(1))  # (row, col) 0-based


def _expand_range(a: str, b: str):
    ra, ca = parse_ref(a)
    rb, cb = parse_ref(b)
    cells = []
    for r in range(min(ra, rb), max(ra, rb) + 1):
        for c in range(min(ca, cb), max(ca, cb) + 1):
            cells.append((r, c))
    return cells


class Sheet:
    """Wraps a {(row,col): raw_string} map and evaluates cells."""

    def __init__(self, raw: dict):
        self.raw = raw                       # {(r,c): "raw text"}
        self._cache: dict = {}
        self._stack: set = set()

    def display(self, r, c) -> str:
        v = self.value(r, c)
        if isinstance(v, float):
            return f"{v:g}"
        return "" if v is None else str(v)

    def value(self, r, c):
        key = (r, c)
        if key in self._cache:
            return self._cache[key]
        if key in self._stack:
            return "#CIRC"
        raw = (self.raw.get(key) or "").strip()
        if raw == "":
            return None
        if not raw.startswith("="):
            try:
                return float(raw)
            except ValueError:
                return raw
        self._stack.add(key)
        try:
            out = self._eval_formula(raw[1:])
        except Exception:  # noqa: BLE001
            out = "#ERR"
        finally:
            self._stack.discard(key)
        self._cache[key] = out
        return out

    def _num(self, r, c) -> float:
        v = self.value(r, c)
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    def _eval_formula(self, expr: str):
        # 1) replace function(range/args) with computed scalars
        def fn_sub(m):
            name = m.group(1).upper()
            args = m.group(2)
            nums = self._collect(args)
            if name == "SUM":
                return repr(sum(nums))
            if name in ("AVERAGE", "AVG"):
                return repr(sum(nums) / len(nums)) if nums else "0"
            if name == "MIN":
                return repr(min(nums)) if nums else "0"
            if name == "MAX":
                return repr(max(nums)) if nums else "0"
            if name == "COUNT":
                return repr(len(nums))
            if name == "PRODUCT":
                p = 1.0
                for n in nums:
                    p *= n
                return repr(p)
            return "0"

        prev = None
        while prev != expr:
            prev = expr
            expr = FUNC_RE.sub(fn_sub, expr)

        # 2) replace bare cell refs with their numeric value
        def ref_sub(m):
            r, c = int(m.group(2)) - 1, col_to_num(m.group(1))
            return repr(self._num(r, c))
        expr = REF_RE.sub(ref_sub, expr)

        # 3) percent literals: 10% -> (10/100)
        expr = re.sub(r"(\d+(?:\.\d+)?)%", r"(\1/100)", expr)

        # 4) safe arithmetic eval
        return self._safe_eval(expr)

    def _collect(self, args: str):
        """Resolve a comma-separated list of ranges/refs/numbers to a flat number list."""
        nums = []
        for part in args.split(","):
            part = part.strip()
            if not part:
                continue
            rng = RANGE_RE.match(part)
            if rng:
                for (r, c) in _expand_range(rng.group(1), rng.group(2)):
                    v = self.value(r, c)
                    if isinstance(v, (int, float)):
                        nums.append(float(v))
                continue
            ref = parse_ref(part)
            if ref:
                v = self.value(*ref)
                if isinstance(v, (int, float)):
                    nums.append(float(v))
                continue
            try:
                nums.append(float(part))
            except ValueError:
                pass
        return nums

    def _safe_eval(self, expr: str):
        node = ast.parse(expr, mode="eval").body
        return self._walk(node)

    def _walk(self, node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError("non-numeric")
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            return _BINOPS[type(node.op)](self._walk(node.left), self._walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = self._walk(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            return 1.0 if self._compare(self._walk(node.left), node.ops[0],
                                        self._walk(node.comparators[0])) else 0.0
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return self._call(node.func.id.upper(), node.args)
        raise ValueError("unsupported expression")

    def _compare(self, a, op, b):
        return {ast.Lt: a < b, ast.Gt: a > b, ast.LtE: a <= b, ast.GtE: a >= b,
                ast.Eq: a == b, ast.NotEq: a != b}.get(type(op), False)

    def _call(self, name, args):
        # IF evaluates its condition then only the chosen branch
        if name == "IF":
            cond = self._walk(args[0])
            return self._walk(args[1] if cond else args[2])
        vals = [self._walk(a) for a in args]
        if name == "ROUND":
            return round(vals[0], int(vals[1]) if len(vals) > 1 else 0)
        if name == "ABS":
            return abs(vals[0])
        if name == "SQRT":
            return vals[0] ** 0.5
        if name == "INT":
            return float(int(vals[0]))
        if name in ("MIN", "MAX"):  # scalar forms (range forms handled earlier)
            return (min if name == "MIN" else max)(vals)
        raise ValueError(f"unknown function {name}")
