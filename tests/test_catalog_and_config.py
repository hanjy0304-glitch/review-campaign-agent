from pathlib import Path

import pytest
import yaml

from review_campaign_agent.catalog import Site, load_catalog
from review_campaign_agent.config import (
    ConfigError,
    load_user_config,
    notify_days,
    required_env_vars,
    resolve_sites,
)

ROOT = Path(__file__).parent.parent


def test_catalog_keys_unique_and_env_safe():
    catalog = load_catalog()
    keys = [s.key for s in catalog]
    assert len(keys) == len(set(keys)) and len(keys) >= 18
    assert all(k.isidentifier() and k == k.lower() for k in keys)


def test_catalog_declares_adapter_level_and_domain_source():
    data = yaml.safe_load((ROOT / "config" / "sites.yaml").read_text(encoding="utf-8"))["sites"]
    assert all(s["adapter"] in ("none", "experimental", "stable") for s in data)
    assert all(s["domain_source"] in ("user", "search", "adapter_tested") for s in data)
    assert "domain_verified" not in (ROOT / "config" / "sites.yaml").read_text(encoding="utf-8")


def test_env_example_lists_every_catalog_site():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    for s in load_catalog():
        assert f"{s.id_env}=" in text and f"{s.pw_env}=" in text


def test_resolve_sites_with_custom_and_unknown_key():
    catalog = [Site("a", "A", "a.kr"), Site("b", "B", "b.kr")]
    sites = resolve_sites(
        {"enabled_sites": ["a"], "custom_sites": [{"key": "mine", "name": "M", "domain": "m.kr"}]}, catalog
    )
    assert [s.key for s in sites] == ["a", "mine"] and sites[1].custom
    with pytest.raises(ConfigError):
        resolve_sites({"enabled_sites": ["zzz"]}, catalog)
    with pytest.raises(ConfigError):
        resolve_sites({}, catalog)


def test_malformed_custom_site_is_a_config_error_not_keyerror():
    with pytest.raises(ConfigError, match="1번째"):
        resolve_sites({"custom_sites": [{"name": "x"}]}, [])


def test_only_enabled_sites_need_credentials():
    names = required_env_vars([Site("assaview", "아싸뷰", "assaview.co.kr")])
    assert "ASSAVIEW_ID" in names and "REVIEWNOTE_ID" not in names


def test_notify_days_defaults_and_overrides():
    assert notify_days({}) == ((3, 1, 0), (1, 0))
    assert notify_days({"notify": {"deadline_reminders_days": [5], "visit_reminders_days": [2]}}) == ((5,), (2,))


def test_user_config_env_var_overrides_file(tmp_path):
    path = tmp_path / "user.yaml"
    path.write_text("enabled_sites: [file]")
    assert load_user_config(path, {"USER_CONFIG": "enabled_sites: [env]"}) == {"enabled_sites": ["env"]}
    assert load_user_config(path, {}) == {"enabled_sites": ["file"]}
    with pytest.raises(ConfigError):
        load_user_config(tmp_path / "missing.yaml", {})


def test_example_user_config_is_valid_yaml_without_unused_keys():
    cfg = yaml.safe_load((ROOT / "config" / "user.example.yaml").read_text(encoding="utf-8"))
    assert {"enabled_sites", "custom_sites", "notify"} <= cfg.keys()
    assert "timezone" not in cfg and "run_times" not in cfg["notify"]
