from math_logic_agent.prompt_templates import build_prompt_template


def test_symbolic_template_shape() -> None:
    prompt = build_prompt_template("symbolic", "solve x^2-4=0", ["ctx1", "ctx2"])
    assert "rigorous math reasoning assistant" in prompt
    assert "User query" in prompt
    assert "Grounded context" in prompt


def test_coding_template_shape() -> None:
    prompt = build_prompt_template("coding", "implement svd", ["ctx"])
    assert "math-coding assistant" in prompt
    assert "typed function signatures" in prompt
