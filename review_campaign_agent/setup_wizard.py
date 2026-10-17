import re
from collections.abc import Callable
from pathlib import Path

import yaml

from .catalog import Site, load_catalog
from .config import USER_CONFIG_PATH, required_env_vars
from .rules import DEFAULT_REMINDER_DAYS

Ask = Callable[[str], str]
Say = Callable[[str], None]


def parse_selection(text: str, count: int) -> list[int]:
    """'1,3,5-7' 또는 'a'(전체) → 0부터 시작하는 인덱스 목록. 빈 입력은 선택 없음."""
    text = text.strip().lower()
    if not text:
        return []
    if text == "a":
        return list(range(count))
    picked: list[int] = []
    for part in text.replace(" ", "").split(","):
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise ValueError(f"이해할 수 없는 입력: {part}")
        start = int(m.group(1))
        end = int(m.group(2) or start)
        if start < 1 or end > count or start > end:
            raise ValueError(f"1~{count} 범위의 번호를 입력하세요: {part}")
        picked += [i - 1 for i in range(start, end + 1)]
    return sorted(set(picked))


def normalize_domain(raw: str) -> str:
    domain = re.sub(r"^https?://", "", raw.strip().lower()).split("/")[0].removeprefix("www.")
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", domain):
        raise ValueError(f"도메인 형식이 아닙니다: {raw}")
    return domain


def make_custom_key(domain: str, taken: set[str]) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", domain.split(".")[0]).strip("_") or "site"
    while key in taken:
        key += "_custom"
    return key


def _ask_sites(ask: Ask, say: Say, catalog: list[Site]) -> list[Site]:
    say("어떤 체험단 사이트를 쓰세요? 아래 목록에서 고르세요.\n")
    for i, s in enumerate(catalog, 1):
        say(f"  {i:>2}. {s.name} ({s.domain})")
    while True:
        raw = ask("\n쓰는 사이트 번호 (예: 1,3,5-7 / 전체 선택: a / 없으면 엔터): ")
        try:
            picked = [catalog[i] for i in parse_selection(raw, len(catalog))]
            break
        except ValueError as e:
            say(str(e))
    return picked


def _ask_custom_sites(ask: Ask, say: Say, taken: set[str]) -> list[Site]:
    if ask("\n위 목록에 없는 체험단 사이트도 쓰세요? (y/N): ").strip().lower() != "y":
        return []
    say("사이트 이름과 주소를 입력하세요. 이름을 비워두면 끝납니다.")
    out: list[Site] = []
    while True:
        name = ask("  사이트 이름: ").strip()
        if not name:
            return out
        try:
            domain = normalize_domain(ask("  사이트 주소 (예: example.co.kr): "))
        except ValueError as e:
            say(f"  {e}")
            continue
        key = make_custom_key(domain, taken)
        taken.add(key)
        out.append(Site(key, name, domain, custom=True))


def _ask_reminder_days(ask: Ask, say: Say) -> list[int]:
    default = ",".join(map(str, DEFAULT_REMINDER_DAYS))
    while True:
        raw = ask(f"\n글 마감 며칠 전에 알릴까요? (기본 {default}, 0=마감 당일): ").strip() or default
        try:
            return sorted({int(x) for x in raw.replace(" ", "").split(",")}, reverse=True)
        except ValueError:
            say("쉼표로 구분한 숫자를 입력하세요. 예: 3,1,0")


def run_setup(
    ask: Ask = input,
    say: Say = print,
    catalog: list[Site] | None = None,
    out_path: Path = USER_CONFIG_PATH,
) -> dict:
    catalog = catalog if catalog is not None else load_catalog()
    if out_path.exists() and ask(f"{out_path.name} 이(가) 이미 있습니다. 덮어쓸까요? (y/N): ").strip().lower() != "y":
        raise SystemExit("설정을 바꾸지 않고 종료합니다.")

    # 1단계: 사용하는 체험단 사이트 (목록 선택 + 목록 밖 사이트 직접 추가)
    while True:
        picked = _ask_sites(ask, say, catalog)
        custom = _ask_custom_sites(ask, say, {s.key for s in catalog})
        if picked or custom:
            break
        say("\n사이트를 하나 이상 선택하거나 추가해야 합니다.\n")

    # 2단계: 내 채널 (선택 사항)
    say("\n내 채널 주소를 입력하세요. 건너뛰려면 엔터.")
    channels: dict = {}
    if blog := ask("  블로그 주소: ").strip():
        channels["blog"] = {"url": blog}
    if insta := ask("  인스타그램 주소: ").strip():
        channels["instagram"] = {"url": insta}

    # 3단계: 알림
    cfg = {
        "channels": channels,
        "timezone": "Asia/Seoul",
        "enabled_sites": [s.key for s in picked],
        "custom_sites": [{"key": s.key, "name": s.name, "domain": s.domain} for s in custom],
        "notify": {
            "run_times": ["09:00", "18:00"],
            "deadline_reminders_days": _ask_reminder_days(ask, say),
            "daily_summary": True,
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    sites = picked + custom
    say(f"\n저장했습니다: {out_path}  (git에 올라가지 않는 파일입니다)")
    say("\n다음으로 아래 값을 .env 파일(내 컴퓨터) 또는 GitHub Settings > Secrets (자동 실행)에 넣으세요.")
    say("비밀번호·토큰은 이 파일이나 채팅에 적지 말고, 값은 직접 입력하세요.\n")
    for name in required_env_vars(sites):
        say(f"  {name}")
    if custom:
        say("\n직접 추가한 사이트는 아직 자동 수집 어댑터가 없습니다. 수동 입력 모드로 동작합니다.")
    return cfg
