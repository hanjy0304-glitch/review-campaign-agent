import argparse
import os

import httpx

from .catalog import CONFIG_DIR, load_catalog
from .config import ConfigError, load_user_config, notify_days, required_env_vars, resolve_sites
from .envfile import load_dotenv
from .notion_store import NotionClient, NotionError, NotionStore, create_database, parse_notion_id
from .probe import format_results, probe_sites
from .rules import today_kst
from .setup_wizard import parse_days, run_setup, run_setup_noninteractive
from .sync import run_sync
from .telegram import NotifyError, TelegramNotifier, find_chat_id


def _env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"환경변수 {name} 가 비어 있습니다. .env 파일 또는 GitHub Secrets 에 넣어 주세요.")
    return value


def check() -> int:
    """설정을 읽어 사용 사이트와 필요한 환경변수 설정 여부를 보여준다. 값은 출력하지 않는다."""
    try:
        sites = resolve_sites(load_user_config())
    except ConfigError as e:
        print(e)
        return 1
    print("사용 사이트:", ", ".join(s.name for s in sites))
    for name in required_env_vars(sites):
        print(f"  {'설정됨' if os.environ.get(name) else '비어있음'}  {name}")
    return 0


def _parse_custom(values: list[str]) -> list[tuple[str, str]]:
    out = []
    for v in values:
        name, sep, domain = v.partition("=")
        if not sep or not name.strip() or not domain.strip():
            raise SystemExit(f"--custom 은 '이름=주소' 형식이어야 합니다: {v}")
        out.append((name.strip(), domain.strip()))
    return out


def _setup(args: argparse.Namespace) -> int:
    if args.sites is None and not args.custom:
        try:
            run_setup()
        except EOFError:
            print("\n입력이 닫혀 있어 질문할 수 없습니다. 옵션으로 실행하세요:")
            print("  python -m review_campaign_agent setup --sites reviewplace,assaview")
            print("사이트 key 는 config/sites.yaml 에 있습니다. 목록에 없으면 --custom '이름=주소'")
            return 1
        return 0
    keys = [k.strip() for k in (args.sites or "").split(",") if k.strip()]
    try:
        run_setup_noninteractive(
            keys,
            custom=_parse_custom(args.custom),
            blog=args.blog,
            instagram=args.instagram,
            reminder_days=parse_days(args.reminder_days),
            visit_reminder_days=parse_days(args.visit_reminder_days),
            catalog=load_catalog(),
            force=args.force,
        )
    except ValueError as e:
        raise SystemExit(str(e)) from None
    return 0


def _notion_init(args: argparse.Namespace) -> int:
    try:
        names = [s.name for s in resolve_sites(load_user_config())]
    except ConfigError:
        names = [s.name for s in load_catalog()]
    try:
        parent = parse_notion_id(args.parent)
        db = create_database(NotionClient(_env("NOTION_TOKEN")), parent, names, args.title)
    except NotionError as e:
        print(e)
        print("'연결'에 이 페이지를 추가했는지 확인하세요 (docs/notion-setup.md 3단계).")
        return 1
    print(f"체험단 관리 표를 만들었습니다: {db['url']}")
    print(f"\n아래 값을 NOTION_DATABASE_ID 로 .env 또는 GitHub Secrets 에 넣으세요:\n  {db['id']}")
    print("\n보기(필터/보드/캘린더)는 Notion 에서 직접 추가하세요. docs/notion-setup.md 5단계를 참고하세요.")
    return 0


def _telegram_chat_id() -> int:
    try:
        chat_id = find_chat_id(_env("TELEGRAM_BOT_TOKEN"))
    except NotifyError as e:
        print(e)
        return 1
    if not chat_id:
        print("받은 메시지가 없습니다. 텔레그램에서 내 봇에게 아무 메시지나 보낸 뒤 다시 실행하세요.")
        return 1
    print(f"TELEGRAM_CHAT_ID 로 아래 값을 넣으세요:\n  {chat_id}")
    return 0


def _telegram_test() -> int:
    try:
        TelegramNotifier(_env("TELEGRAM_BOT_TOKEN"), _env("TELEGRAM_CHAT_ID")).send("✅ 체험단 에이전트 연결 테스트입니다.")
    except NotifyError as e:
        print(e)
        return 1
    print("테스트 메시지를 보냈습니다. 텔레그램을 확인하세요.")
    return 0


def _probe() -> int:
    print(format_results(probe_sites(load_catalog())))
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        reminder_days, visit_days = notify_days(load_user_config())
    except ConfigError:
        reminder_days, visit_days = notify_days({})
    store = NotionStore(NotionClient(_env("NOTION_TOKEN")), _env("NOTION_DATABASE_ID"))
    notifier = None
    if not args.dry_run:
        notifier = TelegramNotifier(_env("TELEGRAM_BOT_TOKEN"), _env("TELEGRAM_CHAT_ID"))
    try:
        result = run_sync(
            store, notifier, today_kst(), reminder_days, visit_days, summary=args.summary, dry_run=args.dry_run
        )
    except (NotionError, httpx.HTTPError) as e:
        print(f"실행 실패: {e if isinstance(e, NotionError) else type(e).__name__}")
        return 1
    print(f"알림 {result.planned}건 계산, {result.sent}건 발송, {result.failed}건 실패")
    return 1 if result.failed else 0


def main() -> int:
    load_dotenv(CONFIG_DIR.parent / ".env")
    parser = argparse.ArgumentParser(prog="review_campaign_agent")
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup", help="사용할 체험단 사이트와 알림 설정 (옵션 없이 실행하면 질문)")
    setup.add_argument("--sites", help="카탈로그 사이트 key, 쉼표 구분 (예: reviewplace,assaview)")
    setup.add_argument("--custom", action="append", default=[], metavar="이름=주소", help="목록에 없는 사이트")
    setup.add_argument("--blog", default="")
    setup.add_argument("--instagram", default="")
    setup.add_argument("--reminder-days", default="3,1,0", help="글 마감 알림 (기본 3,1,0)")
    setup.add_argument("--visit-reminder-days", default="1,0", help="방문일 알림 (기본 1,0)")
    setup.add_argument("--force", action="store_true", help="기존 config/user.yaml 덮어쓰기")
    sub.add_parser("check", help="설정과 필요한 환경변수 확인")
    ni = sub.add_parser("notion-init", help="빈 Notion 페이지 아래에 체험단 관리 표 만들기")
    ni.add_argument("--parent", required=True, help="표를 만들 Notion 페이지 링크 (연결을 추가해 둔 페이지)")
    ni.add_argument("--title", default="체험단 관리")
    sub.add_parser("telegram-chat-id", help="봇에게 메시지를 보낸 뒤 내 chat_id 찾기")
    sub.add_parser("telegram-test", help="텔레그램 연결 테스트 메시지 보내기")
    sub.add_parser("probe", help="로그인 없이 카탈로그 사이트 접속 가능 여부 확인")
    run = sub.add_parser("run", help="Notion 을 읽어 오늘 알림 보내기")
    run.add_argument("--dry-run", action="store_true", help="보내거나 기록하지 않고 내용만 출력")
    run.add_argument("--summary", action="store_true", help="오늘의 할 일 요약도 보내기 (아침 실행용)")
    args = parser.parse_args()
    return {
        "setup": lambda: _setup(args),
        "check": check,
        "notion-init": lambda: _notion_init(args),
        "telegram-chat-id": _telegram_chat_id,
        "telegram-test": _telegram_test,
        "probe": _probe,
        "run": lambda: _run(args),
    }[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
