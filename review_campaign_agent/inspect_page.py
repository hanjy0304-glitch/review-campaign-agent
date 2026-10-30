"""로그인 없이 볼 수 있는 공개 페이지의 구조(링크·입력칸·폼)를 요약한다.

어댑터 개발 첫 단계에서 사이트의 로그인 방식(아이디/비번 vs 소셜)을 파악하는 데 쓴다.
쿠키·계정 정보는 쓰지 않으며, 카탈로그에 있는 도메인만 허용한다.
"""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from .catalog import Site
from .probe import TIMEOUT, USER_AGENT

MAX_LINKS = 60
LOGIN_HINTS = ("login", "signin", "sign-in", "auth", "oauth", "naver", "kakao", "로그인", "회원")


class _Summary(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.links: list[tuple[str, str]] = []
        self.forms: list[dict] = []
        self.inputs: list[str] = []
        self.buttons: list[str] = []
        self._button_text: list[str] | None = None
        self._in_title = False
        self._link_href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "a" and a.get("href"):
            self._link_href, self._link_text = a["href"], []
        elif tag == "form":
            self.forms.append({"action": a.get("action") or "", "method": (a.get("method") or "get").lower()})
        elif tag == "button":
            self._button_text = []
        elif tag == "img" and a.get("alt"):
            self.buttons.append(f"img alt={a['alt'][:30]}")
        elif tag == "input":
            self.inputs.append(f"type={a.get('type') or 'text'} name={a.get('name') or '-'} id={a.get('id') or '-'}")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "button" and self._button_text is not None:
            self.buttons.append("button " + " ".join("".join(self._button_text).split())[:30])
            self._button_text = None
        elif tag == "a" and self._link_href is not None:
            self.links.append((" ".join("".join(self._link_text).split())[:30], self._link_href))
            self._link_href = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._link_href is not None:
            self._link_text.append(data)
        if self._button_text is not None:
            self._button_text.append(data)


def check_allowed(url: str, sites: list[Site]) -> None:
    host = (urlparse(url).hostname or "").lower()
    if urlparse(url).scheme != "https" or not any(host == s.domain or host.endswith("." + s.domain) for s in sites):
        raise ValueError("카탈로그에 있는 사이트의 https 주소만 확인할 수 있습니다.")


def summarize(url: str, sites: list[Site], transport: httpx.BaseTransport | None = None) -> str:
    check_allowed(url, sites)
    with httpx.Client(transport=transport, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}) as client:
        resp = client.get(url, follow_redirects=True)
    check_allowed(str(resp.url), sites)  # 다른 도메인으로 이동했으면 내용을 요약하지 않는다
    return _format(f"HTTP {resp.status_code}", str(resp.url), resp.text)


def summarize_rendered(url: str, sites: list[Site]) -> str:
    """실제 브라우저로 열어 자바스크립트가 그린 뒤의 화면 구조를 요약한다 (playwright 필요)."""
    from playwright.sync_api import sync_playwright

    check_allowed(url, sites)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)
        resp = page.goto(url, wait_until="networkidle", timeout=int(TIMEOUT * 2000))
        html, final, status = page.content(), page.url, resp.status if resp else "?"
        frames = sorted({urlparse(f.url).hostname or "-" for f in page.frames[1:]})
        browser.close()
    check_allowed(final, sites)
    out = _format(f"HTTP {status} (브라우저)", final, html)
    return out + ("\n프레임: " + ", ".join(frames) if frames else "")


def _format(status: str, final_url: str, html: str) -> str:
    parser = _Summary()
    parser.feed(html)
    lines = [f"{status}  최종 주소: {final_url}  제목: {' '.join(parser.title.split())}"]
    lines.append(f"버튼·이미지 {len(parser.buttons)}개: {parser.buttons[:30]}")
    lines.append(f"폼 {len(parser.forms)}개: {parser.forms}")
    lines.append(f"입력칸 {len(parser.inputs)}개:")
    lines += [f"  {i}" for i in parser.inputs[:30]]
    lines.append("로그인 관련 링크:")
    shown = 0
    for text, href in parser.links:
        if any(h in (text + href).lower() for h in LOGIN_HINTS) and shown < MAX_LINKS:
            lines.append(f"  [{text}] {urljoin(final_url, href)}")
            shown += 1
    return "\n".join(lines)
