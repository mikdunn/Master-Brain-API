from pathlib import Path
import sys

ROOT = r"C:/Users/dunnm/Dropbox/Apps/Master Brain"
OUT = Path("config/master_brain.toml")


def main() -> None:
    sys.path.insert(0, r"c:/Users/dunnm/Dropbox/Apps/Master-Brain-API/src")
    import math_logic_agent.master_brain as master_brain

    rendered = master_brain.render_master_module_registry_toml(ROOT)
    OUT.write_text(rendered, encoding="utf-8")
    head = "\n".join(rendered.splitlines()[:10])
    Path("data/reports/render_head.txt").write_text(
        f"{master_brain.__file__}\n---\n{head}\n",
        encoding="utf-8",
    )
    print(OUT.resolve())


if __name__ == "__main__":
    main()
