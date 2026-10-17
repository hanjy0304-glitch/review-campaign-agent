import argparse
import os

from .catalog import load_catalog
from .config import ConfigError, load_user_config, required_env_vars, resolve_sites
from .setup_wizard import parse_days, run_setup, run_setup_noninteractive


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


def main() -> int:
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
    args = parser.parse_args()
    if args.command == "setup":
        return _setup(args)
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
