import pytest
import yaml

from review_campaign_agent.catalog import Site
from review_campaign_agent.setup_wizard import (
    make_custom_key,
    normalize_domain,
    parse_days,
    parse_selection,
    run_setup,
    run_setup_noninteractive,
)

CATALOG = [Site("a", "A", "a.kr"), Site("b", "B", "b.kr", adapter="experimental"), Site("c", "C", "c.kr")]


def scripted(answers):
    it = iter(answers)
    return lambda prompt: next(it)


def test_parse_selection():
    assert parse_selection("1,3", 5) == [0, 2]
    assert parse_selection("2-4", 5) == [1, 2, 3]
    assert parse_selection("a", 3) == [0, 1, 2]
    assert parse_selection("", 3) == []
    for bad in ("0", "6", "x", "3-2"):
        with pytest.raises(ValueError):
            parse_selection(bad, 5)


def test_parse_days_rejects_negative_and_garbage():
    assert parse_days("0, 3,1") == [3, 1, 0]
    for bad in ("-1,3", "x", ""):
        with pytest.raises(ValueError):
            parse_days(bad)


def test_normalize_domain_and_keys():
    assert normalize_domain("https://www.Example.co.kr/path") == "example.co.kr"
    with pytest.raises(ValueError):
        normalize_domain("not a domain")
    assert make_custom_key("example.co.kr", {"example"}) == "example_custom"
    key = make_custom_key("11st.co.kr", set())  # 환경변수 이름이 숫자로 시작하면 안 된다
    assert key == "site_11st" and Site(key, "x", "11st.co.kr").id_env == "SITE_11ST_ID"


def test_first_question_is_site_selection_and_lists_adapter_status(tmp_path):
    prompts, messages = [], []

    def ask(prompt):
        prompts.append(prompt)
        return "1" if len(prompts) == 1 else ""

    run_setup(ask=ask, say=messages.append, catalog=CATALOG, out_path=tmp_path / "user.yaml")
    assert "쓰는 사이트" in prompts[0]
    listing = "\n".join(messages)
    assert "A (a.kr) [수동]" in listing and "B (b.kr) [자동]" in listing


def test_setup_writes_config_with_catalog_and_custom_sites(tmp_path):
    out = tmp_path / "user.yaml"
    answers = [
        "1,3",  # 목록에서 선택
        "y",  # 목록 밖 사이트 있음
        "내 사이트", "https://www.mine.co.kr/x",
        "",  # 입력 종료
        "https://blog.example.com/me",  # 블로그
        "",  # 인스타 건너뜀
        "5,2,0",  # 마감 알림
        "2",  # 방문 알림
    ]
    messages = []
    cfg = run_setup(ask=scripted(answers), say=messages.append, catalog=CATALOG, out_path=out)
    saved = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert saved == cfg
    assert saved["enabled_sites"] == ["a", "c"]
    assert saved["custom_sites"] == [{"key": "mine", "name": "내 사이트", "domain": "mine.co.kr"}]
    assert saved["channels"] == {"blog": {"url": "https://blog.example.com/me"}}
    assert saved["notify"]["deadline_reminders_days"] == [5, 2, 0]
    assert saved["notify"]["visit_reminders_days"] == [2]
    assert "timezone" not in saved and "run_times" not in saved["notify"]
    text = "\n".join(messages)
    assert "A_ID" in text and "MINE_PW" in text and "B_ID" not in text


def test_negative_days_are_asked_again(tmp_path):
    answers = ["1", "n", "", "", "-1,3", "3,1", ""]
    cfg = run_setup(ask=scripted(answers), say=lambda m: None, catalog=CATALOG, out_path=tmp_path / "user.yaml")
    assert cfg["notify"]["deadline_reminders_days"] == [3, 1]


def test_setup_requires_at_least_one_site(tmp_path):
    answers = ["", "n", "2", "n", "", "", "", ""]  # 첫 시도는 선택 없음 → 다시 질문
    cfg = run_setup(ask=scripted(answers), say=lambda m: None, catalog=CATALOG, out_path=tmp_path / "user.yaml")
    assert cfg["enabled_sites"] == ["b"]


def test_setup_does_not_overwrite_without_consent(tmp_path):
    out = tmp_path / "user.yaml"
    out.write_text("keep: me")
    with pytest.raises(SystemExit):
        run_setup(ask=scripted(["n"]), say=lambda m: None, catalog=CATALOG, out_path=out)
    assert out.read_text() == "keep: me"


def test_noninteractive_setup(tmp_path):
    out = tmp_path / "user.yaml"
    cfg = run_setup_noninteractive(
        ["a", "b"], custom=[("My Site", "my.example.kr")], instagram="https://instagram.com/x",
        catalog=CATALOG, out_path=out, say=lambda m: None,
    )
    assert yaml.safe_load(out.read_text(encoding="utf-8")) == cfg
    assert cfg["enabled_sites"] == ["a", "b"] and cfg["custom_sites"][0]["key"] == "my"
    assert cfg["channels"] == {"instagram": {"url": "https://instagram.com/x"}}


def test_noninteractive_guards(tmp_path):
    out = tmp_path / "user.yaml"
    kw = dict(catalog=CATALOG, out_path=out, say=lambda m: None)
    with pytest.raises(SystemExit, match="카탈로그에 없는"):
        run_setup_noninteractive(["zzz"], **kw)
    with pytest.raises(SystemExit, match="하나 이상"):
        run_setup_noninteractive([], **kw)
    out.write_text("keep: me")
    with pytest.raises(SystemExit, match="--force"):
        run_setup_noninteractive(["a"], **kw)
    run_setup_noninteractive(["a"], force=True, **kw)
    assert "enabled_sites" in out.read_text()
