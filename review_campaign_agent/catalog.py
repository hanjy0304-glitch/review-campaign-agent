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
    adapter: str = "none"  # none | experimental | stable. none 이면 Notion 수동 입력으로 사용

    @property
    def id_env(self) -> str:
        return f"{self.key.upper()}_ID"

    @property
    def pw_env(self) -> str:
        return f"{self.key.upper()}_PW"

    @property
    def auto_collect(self) -> bool:
        return self.adapter != "none"


def load_catalog(path: Path | None = None) -> list[Site]:
    data = yaml.safe_load((path or CONFIG_DIR / "sites.yaml").read_text(encoding="utf-8"))
    return [Site(s["key"], s["name"], s["domain"], adapter=s.get("adapter", "none")) for s in data["sites"]]
