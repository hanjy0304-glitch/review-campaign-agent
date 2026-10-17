import pytest
import yaml

from review_campaign_agent.catalog import Site, load_catalog
from review_campaign_agent.config import ConfigError, load_user_config, required_env_vars, resolve_sites


def test_catalog_keys_unique_and_env_safe():
    catalog = load_catalog()
    keys = [s.key for s in catalog]
    assert len(keys) == len(set(keys)) and len(keys) >= 18
    assert all(k.isidentifier() and k == k.lower() for k in keys)


def test_env_example_lists_every_catalog_site():
    from pathlib import Path

    text = (Path(__file__).parent.parent / ".env.example").read_text(encoding="utf-8")
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


def test_only_enabled_sites_need_credentials():
    names = required_env_vars([Site("assaview", "아싸뷰", "assaview.co.kr")])
    assert "ASSAVIEW_ID" in names and "REVIEWNOTE_ID" not in names


def test_user_config_env_var_overrides_file(tmp_path):
    path = tmp_path / "user.yaml"
    path.write_text("enabled_sites: [file]")
    assert load_user_config(path, {"USER_CONFIG": "enabled_sites: [env]"}) == {"enabled_sites": ["env"]}
    assert load_user_config(path, {}) == {"enabled_sites": ["file"]}
    with pytest.raises(ConfigError):
        load_user_config(tmp_path / "missing.yaml", {})


def test_example_user_config_is_valid_yaml():
    from pathlib import Path

    cfg = yaml.safe_load((Path(__file__).parent.parent / "config" / "user.example.yaml").read_text(encoding="utf-8"))
    assert {"enabled_sites", "custom_sites", "notify"} <= cfg.keys()
