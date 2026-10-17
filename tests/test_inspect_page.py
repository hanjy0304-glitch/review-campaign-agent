import httpx
import pytest

from review_campaign_agent.catalog import Site
from review_campaign_agent.inspect_page import summarize

SITES = [Site("a", "A", "ok.example")]
HTML = """<html><head><title> 로그인 </title></head><body>
<a href="/login">로그인</a><a href="/oauth/naver">네이버로 시작</a><a href="/about">소개</a>
<form action="/auth" method="POST"><input type="text" name="uid"><input type="password" name="pw"></form>
</body></html>"""


def test_summarize_finds_login_parts():
    out = summarize("https://ok.example/", SITES, transport=httpx.MockTransport(lambda r: httpx.Response(200, text=HTML)))
    assert "제목: 로그인" in out
    assert "type=password name=pw" in out
    assert "https://ok.example/oauth/naver" in out
    assert "소개" not in out


@pytest.mark.parametrize("url", ["https://evil.example/", "http://ok.example/", "https://notok.example/"])
def test_rejects_unlisted_or_insecure(url):
    with pytest.raises(ValueError):
        summarize(url, SITES)


def test_summarize_lists_buttons_and_images():
    html = '<button> 네이버 로그인 </button><img alt="카카오 로그인" src="x.png">'
    out = summarize("https://ok.example/", SITES, transport=httpx.MockTransport(lambda r: httpx.Response(200, text=html)))
    assert "button 네이버 로그인" in out
    assert "img alt=카카오 로그인" in out
