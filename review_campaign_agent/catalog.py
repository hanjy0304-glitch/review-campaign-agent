from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass(frozen=True)
class Site:
    key: str
    name: str
    domain: str
    custom: bool = False

    @property
    def id_env(self) -> str:
        return f"{self.key.upper()}_ID"

    @property
    def pw_env(self) -> str:
        return f"{self.key.upper()}_PW"


def load_catalog(path: Path | None = None) -> list[Site]:
    data = yaml.safe_load((path or CONFIG_DIR / "sites.yaml").read_text(encoding="utf-8"))
    return [Site(s["key"], s["name"], s["domain"]) for s in data["sites"]]
