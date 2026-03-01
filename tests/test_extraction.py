from math_logic_agent.extraction import extract_equations, is_low_quality_text


def test_extract_equations_finds_math_lines() -> None:
    text = """
    Definition: Let A = U Sigma V^T
    This is prose only.
    x^2 + y^2 = z^2
    """
    eqs = extract_equations(text)
    assert len(eqs) >= 2
    assert any("=" in e for e in eqs)


def test_low_quality_heuristic() -> None:
    assert is_low_quality_text("abc")
    assert not is_low_quality_text("This sentence has enough alphabetic content to be considered valid extracted text.")
