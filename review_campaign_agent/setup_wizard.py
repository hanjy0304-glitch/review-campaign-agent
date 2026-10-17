import re
from collections.abc import Callable, Sequence
from pathlib import Path

import yaml

from .catalog import Site, load_catalog
from .config import USER_CONFIG_PATH, required_env_vars
from .rules import DEFAULT_REMINDER_DAYS, DEFAULT_VISIT_REMINDER_DAYS

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


def parse_days(text: str) -> list[int]:
    """'3,1,0' → [3, 1, 0]. 0 이상의 정수만 허용."""
    try:
        days = {int(x) for x in text.replace(" ", "").split(",")}
    except ValueError:
        raise ValueError("쉼표로 구분한 숫자를 입력하세요. 예: 3,1,0") from None
    if min(days) < 0:
        raise ValueError("0 이상의 숫자만 입력하세요. 0 은 당일입니다.")
    return sorted(days, reverse=True)


def normalize_domain(raw: str) -> str:
    domain = re.sub(r"^https?://", "", raw.strip().lower()).split("/")[0].removeprefix("www.")
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", domain):
        raise ValueError(f"도메인 형식이 아닙니다: {raw}")
    return domain


def make_custom_key(domain: str, taken: set[str]) -> str:
    """도메인에서 환경변수 이름으로 쓸 수 있는 key 를 만든다 (숫자로 시작하면 site_ 를 붙인다)."""
    key = re.sub(r"[^a-z0-9]+", "_", domain.split(".")[0]).strip("_") or "site"
    if key[0].isdigit():
        key = f"site_{key}"
    while key in taken:
        key += "_custom"
    return key


def build_custom_sites(entries: Sequence[tuple[str, str]], taken: set[str]) -> list[Site]:
    taken = set(taken)
    out = []
    for name, raw_domain in entries:
        domain = normalize_domain(raw_domain)
        key = make_custom_key(domain, taken)
        taken.add(key)
        out.append(Site(key, name, domain, custom=True))
    return out


def build_config(
    picked: Sequence[Site],
    custom: Sequence[Site],
    channels: dict,
    reminder_days: Sequence[int] = DEFAULT_REMINDER_DAYS,
    visit_reminder_days: Sequence[int] = DEFAULT_VISIT_REMINDER_DAYS,
) -> dict:
    return {
        "channels": channels,
        "enabled_sites": [s.key for s in picked],
        "custom_sites": [{"key": s.key, "name": s.name, "domain": s.domain} for s in custom],
        "notify": {
            "deadline_reminders_days": list(reminder_days),
            "visit_reminders_days": list(visit_reminder_days),
            "daily_summary": True,
        },
    }


def write_config(cfg: dict, sites: Sequence[Site], out_path: Path, say: Say) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    say(f"\n저장했습니다: {out_path}  (git에 올라가지 않는 파일입니다)")
    say("\n다음으로 아래 값을 .env 파일(내 컴퓨터) 또는 GitHub Settings > Secrets (자동 실행)에 넣으세요.")
    say("비밀번호·토큰은 이 파일이나 채팅에 적지 말고, 값은 직접 입력하세요.\n")
    for name in required_env_vars(list(sites)):
        say(f"  {name}")
    manual = [s.name for s in sites if not s.auto_collect]
    if manual:
        say(f"\n자동 수집이 아직 없는 사이트: {', '.join(manual)}")
        say("→ 선정되면 Notion 표에 직접 입력하세요. 마감일·방문일 알림은 똑같이 받을 수 있습니다.")


def _ask_sites(ask: Ask, say: Say, catalog: list[Site]) -> list[Site]:
    say("어떤 체험단 사이트를 쓰세요? 아래 목록에서 고르세요.")
    say("[자동] = 자동 수집 지원 / [수동] = 선정 내용을 Notion에 직접 입력 (마감·방문 알림은 동일)\n")
    for i, s in enumerate(catalog, 1):
        say(f"  {i:>2}. {s.name} ({s.domain}) {'[자동]' if s.auto_collect else '[수동]'}")
    while True:
        raw = ask("\n쓰는 사이트 번호 (예: 1,3,5-7 / 전체 선택: a / 없으면 엔터): ")
        try:
            return [catalog[i] for i in parse_selection(raw, len(catalog))]
        except ValueError as e:
            say(str(e))


def _ask_custom_sites(ask: Ask, say: Say, taken: set[str]) -> list[Site]:
    if ask("\n위 목록에 없는 체험단 사이트도 쓰세요? (y/N): ").strip().lower() != "y":
        return []
    say("사이트 이름과 주소를 입력하세요. 이름을 비워두면 끝납니다.")
    entries: list[tuple[str, str]] = []
    while True:
        name = ask("  사이트 이름: ").strip()
        if not name:
            return build_custom_sites(entries, taken)
        try:
            domain = normalize_domain(ask("  사이트 주소 (예: example.co.kr): "))
        except ValueError as e:
            say(f"  {e}")
            continue
        entries.append((name, domain))


def _ask_days(ask: Ask, say: Say, question: str, default: Sequence[int]) -> list[int]:
    default_text = ",".join(map(str, default))
    while True:
        raw = ask(f"\n{question} (기본 {default_text}, 0=당일): ").strip() or default_text
        try:
            return parse_days(raw)
        except ValueError as e:
            say(str(e))


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

    # 3단계: 알림 (날짜는 항상 한국시간 기준)
    reminder = _ask_days(ask, say, "글 마감 며칠 전에 알릴까요?", DEFAULT_REMINDER_DAYS)
    visit = _ask_days(ask, say, "방문일 며칠 전에 알릴까요?", DEFAULT_VISIT_REMINDER_DAYS)

    cfg = build_config(picked, custom, channels, reminder, visit)
    write_config(cfg, picked + custom, out_path, say)
    return cfg


def run_setup_noninteractive(
    site_keys: Sequence[str],
    custom: Sequence[tuple[str, str]] = (),
    blog: str = "",
    instagram: str = "",
    reminder_days: Sequence[int] = DEFAULT_REMINDER_DAYS,
    visit_reminder_days: Sequence[int] = DEFAULT_VISIT_REMINDER_DAYS,
    catalog: list[Site] | None = None,
    out_path: Path = USER_CONFIG_PATH,
    force: bool = False,
    say: Say = print,
) -> dict:
    """질문 없이 옵션만으로 설정을 만든다. AI 에이전트·CI 용."""
    catalog = catalog if catalog is not None else load_catalog()
    if out_path.exists() and not force:
        raise SystemExit(f"{out_path.name} 이(가) 이미 있습니다. 덮어쓰려면 --force 를 붙이세요.")
    by_key = {s.key: s for s in catalog}
    unknown = [k for k in site_keys if k not in by_key]
    if unknown:
        raise SystemExit(f"카탈로그에 없는 사이트 key: {', '.join(unknown)}")
    picked = [by_key[k] for k in site_keys]
    custom_sites = build_custom_sites(custom, set(by_key))
    if not picked and not custom_sites:
        raise SystemExit("사이트를 하나 이상 지정하세요 (--sites 또는 --custom).")
    channels: dict = {}
    if blog:
        channels["blog"] = {"url": blog}
    if instagram:
        channels["instagram"] = {"url": instagram}
    cfg = build_config(picked, custom_sites, channels, reminder_days, visit_reminder_days)
    write_config(cfg, picked + custom_sites, out_path, say)
    return cfg
