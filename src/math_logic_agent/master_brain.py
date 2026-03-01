from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_MASTER_BRAIN_ROOT = Path(r"C:\Users\dunnm\Downloads\Master Brain")

_MASTER_BRAIN_RELATIVE_DIRS: tuple[str, ...] = (
    "0_Math_Brain",
    "0_Math_Brain/Algebra",
    "0_Math_Brain/Calculus",
    "0_Math_Brain/Linear_Algebra",
    "0_Math_Brain/Differential_Equations",
    "0_Math_Brain/Probability_and_Stochastic_Processes",
    "0_Math_Brain/Optimization",
    "0_Math_Brain/Numerical_Methods",
    "0_Math_Brain/Logic_and_Proofs",
    "1_Physics_Brain",
    "1_Physics_Brain/Classical_Mechanics",
    "1_Physics_Brain/Thermodynamics_and_Statistical_Mechanics",
    "1_Physics_Brain/Electromagnetism",
    "1_Physics_Brain/Quantum_Physics",
    "1_Physics_Brain/Optics",
    "1_Physics_Brain/Fluid_Dynamics",
    "1_Physics_Brain/Continuum_Mechanics",
    "2_Engineering_Brain",
    "2_Engineering_Brain/Mechanical_Engineering",
    "2_Engineering_Brain/Mechanical_Engineering/Statics",
    "2_Engineering_Brain/Mechanical_Engineering/Dynamics",
    "2_Engineering_Brain/Mechanical_Engineering/Materials",
    "2_Engineering_Brain/Mechanical_Engineering/Thermofluids",
    "2_Engineering_Brain/Electrical_Engineering",
    "2_Engineering_Brain/Electrical_Engineering/Circuits",
    "2_Engineering_Brain/Electrical_Engineering/Signals_and_Systems",
    "2_Engineering_Brain/Electrical_Engineering/Control_Theory",
    "2_Engineering_Brain/Electrical_Engineering/Electromagnetics",
    "2_Engineering_Brain/Chemical_Engineering",
    "2_Engineering_Brain/Chemical_Engineering/Transport",
    "2_Engineering_Brain/Chemical_Engineering/Reaction_Engineering",
    "2_Engineering_Brain/Chemical_Engineering/Thermodynamics",
    "2_Engineering_Brain/Chemical_Engineering/Process_Modeling",
    "2_Engineering_Brain/Biomedical_Engineering",
    "2_Engineering_Brain/Biomedical_Engineering/Biomechanics",
    "2_Engineering_Brain/Biomedical_Engineering/Biomaterials",
    "2_Engineering_Brain/Biomedical_Engineering/Medical_Imaging",
    "2_Engineering_Brain/Biomedical_Engineering/Bioinstrumentation",
    "3_Science_Brain",
    "3_Science_Brain/Biology",
    "3_Science_Brain/Biology/Molecular_Biology",
    "3_Science_Brain/Biology/Genetics",
    "3_Science_Brain/Biology/Genomics",
    "3_Science_Brain/Biology/Bioinformatics",
    "3_Science_Brain/Biology/Systems_Biology",
    "3_Science_Brain/Biology/Biophysics",
    "3_Science_Brain/Biology/Mathematical_Biology",
    "3_Science_Brain/Biology/Ecology",
    "3_Science_Brain/Biology/Evolution",
    "3_Science_Brain/Biology/Microbiology",
    "3_Science_Brain/Biology/Physiology",
    "3_Science_Brain/Biology/Developmental_Biology",
    "3_Science_Brain/Chemistry",
    "3_Science_Brain/Chemistry/General_Chemistry",
    "3_Science_Brain/Chemistry/Organic_Chemistry",
    "3_Science_Brain/Chemistry/Physical_Chemistry",
    "3_Science_Brain/Chemistry/Analytical_Chemistry",
    "3_Science_Brain/Chemistry/Biochemistry",
    "3_Science_Brain/Chemistry/Quantum_Chemistry",
    "3_Science_Brain/Earth_and_Environmental_Sciences",
    "3_Science_Brain/Earth_and_Environmental_Sciences/Geology",
    "3_Science_Brain/Earth_and_Environmental_Sciences/Geophysics",
    "3_Science_Brain/Earth_and_Environmental_Sciences/Geochemistry",
    "3_Science_Brain/Earth_and_Environmental_Sciences/Environmental_Science",
    "3_Science_Brain/Earth_and_Environmental_Sciences/Climate_Science",
    "3_Science_Brain/Physics_of_Life",
    "3_Science_Brain/Physics_of_Life/Cellular_Biophysics",
    "3_Science_Brain/Physics_of_Life/Molecular_Biophysics",
    "3_Science_Brain/Physics_of_Life/Physical_Biology",
    "4_Business_Brain",
    "4_Business_Brain/Accounting",
    "4_Business_Brain/Finance",
    "4_Business_Brain/Finance/Corporate_Finance",
    "4_Business_Brain/Finance/Asset_Pricing",
    "4_Business_Brain/Finance/Derivatives",
    "4_Business_Brain/Finance/Portfolio_Theory",
    "4_Business_Brain/Economics",
    "4_Business_Brain/Economics/Microeconomics",
    "4_Business_Brain/Economics/Macroeconomics",
    "4_Business_Brain/Economics/Game_Theory",
    "4_Business_Brain/Economics/Industrial_Organization",
    "4_Business_Brain/Econometrics",
    "4_Business_Brain/Econometrics/Statistical_Inference",
    "4_Business_Brain/Econometrics/Time_Series",
    "4_Business_Brain/Econometrics/Causal_Inference",
    "4_Business_Brain/Fintech",
    "4_Business_Brain/Technical_Analysis",
    "5_Computer_Science_Brain",
    "5_Computer_Science_Brain/Algorithms",
    "5_Computer_Science_Brain/Data_Structures",
    "5_Computer_Science_Brain/Operating_Systems",
    "5_Computer_Science_Brain/Compilers",
    "5_Computer_Science_Brain/Distributed_Systems",
    "5_Computer_Science_Brain/Machine_Learning",
    "5_Computer_Science_Brain/Deep_Learning",
    "5_Computer_Science_Brain/Reinforcement_Learning",
    "5_Computer_Science_Brain/Probabilistic_Modeling",
    "5_Computer_Science_Brain/Scientific_Computing",
)


@dataclass(frozen=True, slots=True)
class ScaffoldSummary:
    root: Path
    total_directories: int
    created_directories: int
    existing_directories: int


def scaffold_master_brain_structure(root: str | Path = DEFAULT_MASTER_BRAIN_ROOT) -> ScaffoldSummary:
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)

    created = 0
    existing = 0
    for rel in _MASTER_BRAIN_RELATIVE_DIRS:
        p = root_path / rel
        if p.exists():
            existing += 1
        else:
            p.mkdir(parents=True, exist_ok=True)
            created += 1

    return ScaffoldSummary(
        root=root_path,
        total_directories=len(_MASTER_BRAIN_RELATIVE_DIRS),
        created_directories=created,
        existing_directories=existing,
    )


def render_master_module_registry_toml(root: str | Path = DEFAULT_MASTER_BRAIN_ROOT) -> str:
    r = Path(root)
    return f"""schema_version = 1

[modules.math_brain]
display_name = "Math Brain"
paths = [
  "{(r / '0_Math_Brain').as_posix()}",
  "{(r / 'Math Brain').as_posix()}",
]
enabled = true
stage = "active"
priority = 10
aliases = ["math", "proof", "calculus", "linear algebra"]

[modules.physics_brain]
display_name = "Physics Brain"
paths = [
  "{(r / '1_Physics_Brain').as_posix()}",
  "{(r / 'Physics Brain').as_posix()}",
]
enabled = true
stage = "active"
priority = 20
aliases = ["physics", "mechanics", "electromagnetism", "quantum"]

[modules.engineering_brain]
display_name = "Engineering Brain"
paths = [
  "{(r / '2_Engineering_Brain').as_posix()}",
  "{(r / 'Engineering Brain').as_posix()}",
]
enabled = true
stage = "active"
priority = 30
aliases = ["engineering", "design", "control", "thermofluids"]

[modules.science_brain]
display_name = "Science Brain"
paths = [
  "{(r / '3_Science_Brain').as_posix()}",
  "{(r / 'Science Brain').as_posix()}",
]
enabled = true
stage = "active"
priority = 40
aliases = ["biology", "chemistry", "geology", "environment", "life science"]

[modules.business_brain]
display_name = "Business Brain"
paths = [
  "{(r / '4_Business_Brain').as_posix()}",
  "{(r / 'Business Brain').as_posix()}",
]
enabled = true
stage = "active"
priority = 50
aliases = ["business", "finance", "economics", "accounting", "econometrics"]

[modules.cs_brain]
display_name = "Computer Science Brain"
paths = [
  "{(r / '5_Computer_Science_Brain').as_posix()}",
  "{(r / 'Computer Science Brain').as_posix()}",
]
enabled = true
stage = "active"
priority = 60
aliases = ["computer science", "algorithms", "ml", "deep learning", "systems"]
"""


def write_master_module_registry(config_path: str | Path, root: str | Path = DEFAULT_MASTER_BRAIN_ROOT, overwrite: bool = True) -> Path:
    out = Path(config_path)
    if out.exists() and not overwrite:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_master_module_registry_toml(root), encoding="utf-8")
    return out
