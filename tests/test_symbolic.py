from math_logic_agent.symbolic import symbolic_from_query


def test_symbolic_solve() -> None:
    result = symbolic_from_query("solve x^2-4=0 for x")
    assert result.success
    assert result.task == "solve"
    assert "2" in result.output


def test_symbolic_simplify() -> None:
    result = symbolic_from_query("simplify (x**2 - 1)/(x - 1)")
    assert result.success
    assert result.task == "simplify"
    assert "x + 1" in result.output


def test_symbolic_verify() -> None:
    result = symbolic_from_query("(x+1)**2 = x**2 + 2*x + 1")
    assert result.success
    assert result.task == "verify"
    assert "PASS" in result.output
