import os
from collections.abc import Mapping
from pathlib import Path

import yaml

from .catalog import CONFIG_DIR, Site, load_catalog

USER_CONFIG_PATH = CONFIG_DIR / "user.yaml"
COMMON_ENV_VARS = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "NOTION_TOKEN", "NOTION_DATABASE_ID"]


class ConfigError(Exception):
    pass


def load_user_config(
    path: Path = USER_CONFIG_PATH, env: Mapping[str, str] | None = None
) -> dict:
    """USER_CONFIG 환경변수(GitHub Actions Variables)가 있으면 우선, 없으면 config/user.yaml."""
    env = os.environ if env is None else env
    if env.get("USER_CONFIG"):
        return yaml.safe_load(env["USER_CONFIG"]) or {}
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raise ConfigError("사용자 설정이 없습니다. `python -m review_campaign_agent setup` 을 먼저 실행하세요.")


def resolve_sites(cfg: dict, catalog: list[Site] | None = None) -> list[Site]:
    catalog = catalog if catalog is not None else load_catalog()
    by_key = {s.key: s for s in catalog}
    unknown = [k for k in cfg.get("enabled_sites") or [] if k not in by_key]
    if unknown:
        raise ConfigError(f"카탈로그에 없는 사이트 key: {', '.join(unknown)}")
    sites = [by_key[k] for k in cfg.get("enabled_sites") or []]
    for c in cfg.get("custom_sites") or []:
        sites.append(Site(c["key"], c["name"], c["domain"], custom=True))
    if not sites:
        raise ConfigError("사용할 사이트가 하나도 없습니다. enabled_sites 또는 custom_sites 를 채우세요.")
    return sites


def required_env_vars(sites: list[Site]) -> list[str]:
    names = list(COMMON_ENV_VARS)
    for s in sites:
        names += [s.id_env, s.pw_env]
    return names
