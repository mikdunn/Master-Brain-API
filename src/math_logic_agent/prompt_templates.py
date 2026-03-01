from __future__ import annotations


def build_prompt_template(mode: str, query: str, context_blocks: list[str]) -> str:
    context = "\n\n".join(context_blocks[:5]) if context_blocks else "No relevant context found."

    if mode == "symbolic":
        return (
            "You are a rigorous math reasoning assistant.\n"
            "Follow this format:\n"
            "1) Identify knowns/unknowns\n"
            "2) Show symbolic steps\n"
            "3) Verify transformation correctness\n"
            "4) Provide final result clearly\n\n"
            f"User query: {query}\n\n"
            f"Grounded context:\n{context}"
        )

    if mode == "coding":
        return (
            "You are a math-coding assistant.\n"
            "Return production-quality Python with brief explanation.\n"
            "Include:\n"
            "- typed function signatures\n"
            "- edge-case handling\n"
            "- tiny runnable example\n\n"
            f"User query: {query}\n\n"
            f"Grounded context:\n{context}"
        )

    if mode == "exam":
        return (
            "You are an exam coach.\n"
            "Generate:\n"
            "- 1 conceptual question\n"
            "- 1 computational question\n"
            "- concise worked solutions\n\n"
            f"User query: {query}\n\n"
            f"Grounded context:\n{context}"
        )

    return (
        "You are a precise teaching assistant.\n"
        "Explain in plain language, then include compact formal detail.\n"
        "Prefer correctness and clarity over verbosity.\n\n"
        f"User query: {query}\n\n"
        f"Grounded context:\n{context}"
    )
