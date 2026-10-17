import pytest
import yaml

from review_campaign_agent.catalog import Site
from review_campaign_agent.setup_wizard import make_custom_key, normalize_domain, parse_selection, run_setup

CATALOG = [Site("a", "A", "a.kr"), Site("b", "B", "b.kr"), Site("c", "C", "c.kr")]


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


def test_normalize_domain_and_key():
    assert normalize_domain("https://www.Example.co.kr/path") == "example.co.kr"
    with pytest.raises(ValueError):
        normalize_domain("not a domain")
    assert make_custom_key("example.co.kr", {"example"}) == "example_custom"


def test_first_question_is_site_selection(tmp_path):
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        return "1" if len(prompts) == 1 else ""

    run_setup(ask=ask, say=lambda m: None, catalog=CATALOG, out_path=tmp_path / "user.yaml")
    assert "쓰는 사이트" in prompts[0]


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
    ]
    messages = []
    cfg = run_setup(ask=scripted(answers), say=messages.append, catalog=CATALOG, out_path=out)
    saved = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert saved == cfg
    assert saved["enabled_sites"] == ["a", "c"]
    assert saved["custom_sites"] == [{"key": "mine", "name": "내 사이트", "domain": "mine.co.kr"}]
    assert saved["channels"] == {"blog": {"url": "https://blog.example.com/me"}}
    assert saved["notify"]["deadline_reminders_days"] == [5, 2, 0]
    text = "\n".join(messages)
    assert "A_ID" in text and "MINE_PW" in text and "B_ID" not in text


def test_setup_requires_at_least_one_site(tmp_path):
    answers = ["", "n", "2", "n", "", "", ""]  # 첫 시도는 선택 없음 → 다시 질문
    cfg = run_setup(ask=scripted(answers), say=lambda m: None, catalog=CATALOG, out_path=tmp_path / "user.yaml")
    assert cfg["enabled_sites"] == ["b"]


def test_setup_does_not_overwrite_without_consent(tmp_path):
    out = tmp_path / "user.yaml"
    out.write_text("keep: me")
    with pytest.raises(SystemExit):
        run_setup(ask=scripted(["n"]), say=lambda m: None, catalog=CATALOG, out_path=out)
    assert out.read_text() == "keep: me"
