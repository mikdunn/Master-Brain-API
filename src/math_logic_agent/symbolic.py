from __future__ import annotations

import re
from dataclasses import dataclass

import sympy as sp


@dataclass(slots=True)
class SymbolicResult:
    task: str
    success: bool
    output: str


def _guess_symbol(expr: str) -> sp.Symbol:
    names = sorted({str(s) for s in sp.sympify(expr).free_symbols})
    if names:
        return sp.Symbol(names[0])
    return sp.Symbol("x")


def _extract_after_keyword(query: str, keyword: str) -> str:
    idx = query.lower().find(keyword)
    if idx < 0:
        return query
    return query[idx + len(keyword) :].strip(" :")


def symbolic_from_query(query: str) -> SymbolicResult:
    q = query.strip()
    lower = q.lower()

    # solve <expr=expr> [for x]
    if "solve" in lower and "=" in q:
        body = _extract_after_keyword(q, "solve")
        var_match = re.search(r"\bfor\s+([a-zA-Z]\w*)\b", body, flags=re.IGNORECASE)
        if var_match:
            var_name = var_match.group(1)
            body = re.sub(r"\bfor\s+[a-zA-Z]\w*\b", "", body, flags=re.IGNORECASE).strip()
            symbol = sp.Symbol(var_name)
        else:
            symbol = sp.Symbol("x")

        left, right = body.split("=", maxsplit=1)
        eq = sp.Eq(sp.sympify(left.strip()), sp.sympify(right.strip()))
        sol = sp.solve(eq, symbol)
        return SymbolicResult(task="solve", success=True, output=f"Solutions for {symbol}: {sol}")

    # simplify <expr>
    if lower.startswith("simplify"):
        expr = _extract_after_keyword(q, "simplify")
        simp = sp.simplify(sp.sympify(expr))
        return SymbolicResult(task="simplify", success=True, output=f"Simplified: {simp}")

    # diff <expr> [w.r.t x]
    if lower.startswith("diff") or "derivative" in lower:
        expr = _extract_after_keyword(q, "diff") if lower.startswith("diff") else q
        expr = re.sub(r"\bderivative\s+of\b", "", expr, flags=re.IGNORECASE).strip()
        wrt = re.search(r"\b(?:wrt|with respect to)\s+([a-zA-Z]\w*)\b", expr, flags=re.IGNORECASE)
        if wrt:
            var = sp.Symbol(wrt.group(1))
            expr = re.sub(r"\b(?:wrt|with respect to)\s+[a-zA-Z]\w*\b", "", expr, flags=re.IGNORECASE).strip()
        else:
            var = _guess_symbol(expr)
        deriv = sp.diff(sp.sympify(expr), var)
        return SymbolicResult(task="differentiate", success=True, output=f"d/d{var}: {deriv}")

    # integrate <expr> [w.r.t x]
    if lower.startswith("integrate") or "integral" in lower:
        expr = _extract_after_keyword(q, "integrate") if lower.startswith("integrate") else q
        expr = re.sub(r"\b(?:integral|of)\b", "", expr, flags=re.IGNORECASE).strip()
        wrt = re.search(r"\b(?:wrt|with respect to)\s+([a-zA-Z]\w*)\b", expr, flags=re.IGNORECASE)
        if wrt:
            var = sp.Symbol(wrt.group(1))
            expr = re.sub(r"\b(?:wrt|with respect to)\s+[a-zA-Z]\w*\b", "", expr, flags=re.IGNORECASE).strip()
        else:
            var = _guess_symbol(expr)
        integ = sp.integrate(sp.sympify(expr), var)
        return SymbolicResult(task="integrate", success=True, output=f"∫ d{var}: {integ}")

    if "=" in q:
        left, right = q.split("=", maxsplit=1)
        lhs = sp.sympify(left.strip())
        rhs = sp.sympify(right.strip())
        ok = sp.simplify(lhs - rhs) == 0
        return SymbolicResult(task="verify", success=True, output=("Verification: PASS" if ok else "Verification: FAIL"))

    return SymbolicResult(
        task="unparsed",
        success=False,
        output="Could not parse symbolic intent. Try: solve x^2-4=0 for x, simplify ..., diff ..., integrate ...",
    )
