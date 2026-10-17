import argparse
import os

from .config import ConfigError, load_user_config, required_env_vars, resolve_sites
from .setup_wizard import run_setup


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="review_campaign_agent")
    parser.add_argument("command", choices=["setup", "check"])
    args = parser.parse_args()
    if args.command == "setup":
        run_setup()
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
