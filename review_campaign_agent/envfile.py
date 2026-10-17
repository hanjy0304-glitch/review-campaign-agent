import os
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """KEY=VALUE 줄을 환경변수로 읽는다. 이미 설정된 값은 덮어쓰지 않는다 (GitHub Secrets 우선)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        if value:
            os.environ.setdefault(key.strip(), value)
