from pathlib import Path
from typing import Any
from collections import Counter

import math_logic_agent.master_brain as master_brain
from math_logic_agent.config import load_module_registry
from math_logic_agent.master_brain import (
    render_master_module_registry_toml,
    scaffold_master_brain_structure,
    write_master_module_registry,
)


def test_scaffold_master_brain_structure_creates_template_dirs(
    tmp_path: Path,
) -> None:
    summary = scaffold_master_brain_structure(tmp_path)
    assert summary.total_directories > 50
    assert summary.created_directories == summary.total_directories
    assert summary.existing_directories == 0
    assert (tmp_path / "6_Humanities_Brain").exists()
    assert (tmp_path / "6_Humanities_Brain" / "Philosophy").exists()
    assert (tmp_path / "6_Humanities_Brain" / "History").exists()
    assert (tmp_path / "6_Humanities_Brain" / "Literature").exists()
    assert (tmp_path / "6_Humanities_Brain" / "Linguistics").exists()
    assert (tmp_path / "6_Humanities_Brain" / "Arts").exists()
    assert (tmp_path / "6_Humanities_Brain" / "Religion").exists()

    summary2 = scaffold_master_brain_structure(tmp_path)
    assert summary2.created_directories == 0
    assert summary2.existing_directories == summary2.total_directories


def test_render_and_load_master_registry(tmp_path: Path) -> None:
    toml_text = render_master_module_registry_toml(tmp_path)
    assert "[alias_noise]" in toml_text
    assert "onlinelibrary" in toml_text
    cfg = tmp_path / "master_brain.toml"
    cfg.write_text(toml_text, encoding="utf-8")

    reg = load_module_registry(cfg)
    assert reg.schema_version == 1
    assert len(reg.modules) == 7
    ids = {m.module_id for m in reg.modules}
    assert ids == {
        "math_brain",
        "physics_brain",
        "engineering_brain",
        "science_brain",
        "business_brain",
        "cs_brain",
        "humanities_brain",
    }


def test_write_master_registry_respects_overwrite_flag(tmp_path: Path) -> None:
    cfg = tmp_path / "master.toml"
    write_master_module_registry(cfg, root=tmp_path, overwrite=True)
    first = cfg.read_text(encoding="utf-8")

    cfg.write_text("schema_version = 999\n", encoding="utf-8")
    write_master_module_registry(cfg, root=tmp_path, overwrite=False)
    assert cfg.read_text(encoding="utf-8") == "schema_version = 999\n"

    write_master_module_registry(cfg, root=tmp_path, overwrite=True)
    assert cfg.read_text(encoding="utf-8") == first


def test_render_master_registry_discovers_recursive_subject_subfolders(
    tmp_path: Path,
) -> None:
    humanities = tmp_path / "Humanities Brain"
    comms = humanities / "Communication, Writing, Professional Development"
    nested = comms / "Career Growth"
    arts = humanities / "Art, Music, and Culture"
    religion = humanities / "Religion"
    philosophy = humanities / "Philosophy"

    physics = tmp_path / "1_Physics_Brain"
    qft = physics / "Quantum Physics" / "Quantum Field Theory"

    for d in (comms, nested, arts, religion, philosophy, qft):
        d.mkdir(parents=True, exist_ok=True)

    cfg = tmp_path / "master_brain.toml"
    cfg.write_text(
        render_master_module_registry_toml(tmp_path),
        encoding="utf-8",
    )
    reg = load_module_registry(cfg)

    module_by_id = {m.module_id: m for m in reg.modules}

    humanities_module = module_by_id["humanities_brain"]
    assert tuple(str(p.as_posix()) for p in humanities_module.paths) == (
        humanities.as_posix(),
    )
    assert 10 <= len(humanities_module.aliases) <= 20

    comms_module = module_by_id[
        "humanities_brain_communication_writing_professional_development"
    ]
    assert tuple(str(p.as_posix()) for p in comms_module.paths) == (
        comms.as_posix(),
    )
    assert 10 <= len(comms_module.aliases) <= 20

    nested_module = module_by_id[
        (
            "humanities_brain_communication_writing_"
            "professional_development_career_growth"
        )
    ]
    assert tuple(str(p.as_posix()) for p in nested_module.paths) == (
        nested.as_posix(),
    )

    qft_module = module_by_id[
        "physics_brain_quantum_physics_quantum_field_theory"
    ]
    assert tuple(str(p.as_posix()) for p in qft_module.paths) == (
        qft.as_posix(),
    )
    assert 10 <= len(qft_module.aliases) <= 20


def test_render_master_registry_excludes_nonexistent_paths(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "3_Science_Brain" / "Biology"
    root_b = tmp_path / "Science Brain" / "Biology"
    existing = root_b / "Mathematical Biology"

    root_a.mkdir(parents=True, exist_ok=True)
    existing.mkdir(parents=True, exist_ok=True)

    cfg = tmp_path / "master_brain.toml"
    cfg.write_text(
        render_master_module_registry_toml(tmp_path),
        encoding="utf-8",
    )
    reg = load_module_registry(cfg)
    module_by_id = {m.module_id: m for m in reg.modules}

    mathematical_bio = module_by_id[
        "science_brain_biology_mathematical_biology"
    ]
    assert tuple(str(p.as_posix()) for p in mathematical_bio.paths) == (
        existing.as_posix(),
    )
    assert 10 <= len(mathematical_bio.aliases) <= 20


def test_term_mining_aliases_are_field_specific_and_not_course_code_only(
    tmp_path: Path,
) -> None:
    biology = tmp_path / "Science Brain" / "Biology" / "MCDB614"
    biology.mkdir(parents=True, exist_ok=True)
    notes = biology / "lecture_notes.md"
    notes.write_text(
        "\n".join(
            [
                "# Gene Regulation in Eukaryotes",
                "## DNA Repair Pathways",
                "## Chromatin Remodeling and Transcription",
                "## Protein Folding and Cellular Stress Response",
            ]
        ),
        encoding="utf-8",
    )

    cfg = tmp_path / "master_brain.toml"
    cfg.write_text(
        render_master_module_registry_toml(tmp_path),
        encoding="utf-8",
    )
    reg = load_module_registry(cfg)
    module_by_id = {m.module_id: m for m in reg.modules}

    module = module_by_id["science_brain_biology_mcdb614"]
    aliases = {a.lower() for a in module.aliases}

    assert not any(a == "mcdb614" for a in aliases)
    assert any(
        any(term in a for term in ("gene", "dna", "chromatin", "protein"))
        for a in aliases
    )


def test_pdf_front_3000_words_mining(tmp_path: Path) -> None:
    bio = tmp_path / "Science Brain" / "Biology" / "Advanced Topics"
    bio.mkdir(parents=True, exist_ok=True)
    pdf_path = bio / "front_matter.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%mock\n")

    class _MockPage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _MockPdfReader:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _unused: tuple[tuple[Any, ...], dict[str, Any]] = (args, kwargs)
            _ = _unused
            self.outline = []
            repeated = "gene regulation dna repair chromatin remodeling "
            self.pages = [_MockPage(repeated * 200)]

    original_reader = master_brain.PdfReader
    master_brain.PdfReader = _MockPdfReader
    try:
        cfg = tmp_path / "master_brain.toml"
        cfg.write_text(
            render_master_module_registry_toml(tmp_path),
            encoding="utf-8",
        )
    finally:
        master_brain.PdfReader = original_reader

    reg = load_module_registry(cfg)
    module = {
        m.module_id: m for m in reg.modules
    }["science_brain_biology_advanced_topics"]
    aliases = {a.lower() for a in module.aliases}
    assert any(
        any(token in t for token in ("gene", "regulation", "dna", "repair"))
        for t in aliases
    )


def test_grad_reranker_boosts_deeper_modules() -> None:
    counts = Counter(
        {
            "random process": 5,
            "bayesian inference": 3,
            "stochastic modeling": 3,
        }
    )
    global_df = Counter({k: 1 for k in counts})

    shallow = master_brain.select_specific_terms_for_aliases(
        counts,
        global_df,
        brain_module_id="science_brain",
        depth=1,
        limit=1,
    )
    deep = master_brain.select_specific_terms_for_aliases(
        counts,
        global_df,
        brain_module_id="science_brain",
        depth=4,
        limit=1,
    )

    assert shallow == ["random process"]
    assert deep[0] in {"bayesian inference", "stochastic modeling"}


def test_noisy_lab_shorthand_detector_allows_lab_tokens() -> None:
    assert not master_brain.is_noisy_lab_shorthand_term("leu2 mutants")
    assert not master_brain.is_noisy_lab_shorthand_term("ade2-1 strain")
    assert not master_brain.is_noisy_lab_shorthand_term("dna repair pathway")


def test_specific_term_selector_keeps_lab_tokens_but_drops_structural_noise(
) -> None:
    path_like = (
        "bioinformatics / slides / article / "
        "history and scope of bioinformatics"
    )
    counts = Counter(
        {
            "leu2 mutants": 9,
            "rnhab mutants": 8,
            "rnhab": 7,
            "(stanford encyclopedia philosophy)": 10,
            path_like: 8,
            "dna repair pathway": 4,
            "chromatin regulation": 3,
        }
    )
    global_df = Counter({k: 1 for k in counts})

    selected = master_brain.select_specific_terms_for_aliases(
        counts,
        global_df,
        brain_module_id="science_brain",
        depth=3,
        limit=3,
    )

    assert any(
        token in selected
        for token in ("leu2 mutants", "rnhab mutants", "rnhab")
    )
    assert "(stanford encyclopedia philosophy)" not in selected
    assert path_like not in selected
    assert "dna repair pathway" in selected


def test_rendered_aliases_drop_parenthetical_and_path_like_terms(
    tmp_path: Path,
) -> None:
    target = (
        tmp_path
        / "Science Brain"
        / "Bioinformatics"
        / "Slides"
        / "Article"
        / "History and Scope of Bioinformatics"
    )
    target.mkdir(parents=True, exist_ok=True)
    (target / "source.md").write_text(
        "\n".join(
            [
                "# (Stanford Encyclopedia Philosophy)",
                "# DNA Repair Pathway",
                "# LEU2 mutants and ADE2-1 strain markers",
            ]
        ),
        encoding="utf-8",
    )

    cfg = tmp_path / "master_brain.toml"
    cfg.write_text(
        render_master_module_registry_toml(tmp_path),
        encoding="utf-8",
    )
    reg = load_module_registry(cfg)
    module = {
        m.module_id: m for m in reg.modules
    }[
        (
            "science_brain_bioinformatics_slides_article_"
            "history_and_scope_of_bioinformatics"
        )
    ]

    lowered = {a.lower() for a in module.aliases}
    assert not any(a.startswith("(") for a in lowered)
    assert not any(" / " in a for a in lowered)
    assert any(
        marker in " ".join(lowered)
        for marker in ("leu2", "ade2", "dna repair")
    )


def test_rendered_aliases_drop_publisher_and_episode_noise(
    tmp_path: Path,
) -> None:
    target = (
        tmp_path
        / "Humanities Brain"
        / "General Science for General Knowledge"
        / "Anthropology"
    )
    target.mkdir(parents=True, exist_ok=True)
    (target / "source.md").write_text(
        "\n".join(
            [
                "# OnlineLibrary Wiley",
                "# Episode",
                "# Genetic Testing",
            ]
        ),
        encoding="utf-8",
    )

    cfg = tmp_path / "master_brain.toml"
    cfg.write_text(
        render_master_module_registry_toml(tmp_path),
        encoding="utf-8",
    )
    reg = load_module_registry(cfg)
    module = {
        m.module_id: m for m in reg.modules
    }[
        (
            "humanities_brain_general_science_for_general_"
            "knowledge_anthropology"
        )
    ]

    lowered = {a.lower() for a in module.aliases}
    joined = " ".join(lowered)
    assert "onlinelibrary" not in joined
    assert "wiley" not in joined
    assert "episode notes" not in lowered
    assert any("genetic testing" in a for a in lowered)


def test_rendered_aliases_drop_numbered_and_edition_noise(
    tmp_path: Path,
) -> None:
    target = tmp_path / "Business Brain" / "Economics"
    target.mkdir(parents=True, exist_ok=True)
    (target / "source.md").write_text(
        "\n".join(
            [
                "# 13 Risky Assets",
                "# 0129302",
                "# Pearson 2010",
                "# Risk Forecast",
            ]
        ),
        encoding="utf-8",
    )

    cfg = tmp_path / "master_brain.toml"
    cfg.write_text(
        render_master_module_registry_toml(tmp_path),
        encoding="utf-8",
    )
    reg = load_module_registry(cfg)
    economics = {
        m.module_id: m for m in reg.modules
    }["business_brain_economics"]
    joined = " ".join(a.lower() for a in economics.aliases)

    assert "pearson" not in joined
    assert "0129302" not in joined
    assert "13 risky" not in joined
    assert "risk forecast" in joined


def test_write_registry_preserves_custom_alias_noise_terms(
    tmp_path: Path,
) -> None:
    cfg = tmp_path / "master_brain.toml"
    cfg.write_text(
        "\n".join(
            [
                "schema_version = 1",
                "",
                "[alias_noise]",
                'terms = ["customnoise"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    root = tmp_path / "Humanities Brain" / "Classics"
    root.mkdir(parents=True, exist_ok=True)
    (root / "doc.md").write_text("# CustomNoise", encoding="utf-8")

    write_master_module_registry(cfg, root=tmp_path, overwrite=True)
    text = cfg.read_text(encoding="utf-8")
    assert "[alias_noise]" in text
    assert '"customnoise"' in text

    reg = load_module_registry(cfg)
    classics = {
        m.module_id: m for m in reg.modules
    }["humanities_brain_classics"]
    assert all("customnoise" not in a.lower() for a in classics.aliases)
