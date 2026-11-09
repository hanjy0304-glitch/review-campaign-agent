"""리뷰플레이스(reviewplace.co.kr) 서버 수집기.

- 로그인: `/bbs/login.php` 폼 → `/bbs/login_check.php` (mb_id, mb_password, url, auto_login)
- 선정 목록: `/my/cmp_select.php`
- 파싱 기준은 크롬 확장(`extension/src/reviewplace_parse.js`)과 같다. 클래스 이름은 자주 바뀌므로
  링크 주소(`/pr/?id=번호`)와 'D-n'·'오늘마감' 문구로 카드를 찾는다.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from ..models import Campaign, Status
from .base import CollectError, Collector, LoginError

KEY = "reviewplace"
NAME = "리뷰플레이스"
ORIGIN = "https://www.reviewplace.co.kr"

DDAY_RE = re.compile(r"D\s*-\s*\d+|오늘\s*마감|D\s*\+\s*\d+")
APPLY_RE = re.compile(r"신청\s*\d+")
LINK_RE = re.compile(r"[?&]id=(\d+)")
KINDS = ("구매평", "기자단")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def days_left(text: str) -> int | None:
    """카드 문구에서 남은 일수. D-3 → 3, 오늘마감 → 0, D+2(마감 지남) → -2."""
    text = _norm(text)
    m = re.search(r"D\s*-\s*(\d+)", text)
    if m:
        return int(m.group(1))
    if "오늘" in text and "마감" in text:
        return 0
    m = re.search(r"D\s*\+\s*(\d+)", text)
    return -int(m.group(1)) if m else None


def _path(href: str) -> str:
    """절대 주소를 사이트 안 경로로 바꾼다 (Notion 링크 칸은 한 가지 형태로 둔다)."""
    if href.startswith("http"):
        parts = urlsplit(href)
        return parts.path + (f"?{parts.query}" if parts.query else "")
    return href if href.startswith("/") else "/" + href


def _card_for(anchor):
    """링크가 속한 카드 덩어리: 링크가 하나뿐이면서 마감 문구를 담은 가장 작은 상위 요소."""
    el = anchor
    while el is not None and getattr(el, "name", None) != "[document]":
        if DDAY_RE.search(_norm(el.get_text(" "))) and len(el.select('a[href*="/pr/?id="]')) == 1:
            return el
        el = el.parent
    return anchor


def _title_and_provided(card) -> tuple[str, str]:
    """카드의 문단 순서로 제목과 제공내역을 읽는다 (마감·신청수 문단은 제외)."""
    texts = [_norm(p.get_text(" ")) for p in card.find_all("p")]
    texts = [t for t in texts if t]
    if not texts:
        return _norm(card.get_text(" ")), ""
    title = texts[0]
    provided = next(
        (t for t in texts[1:] if not DDAY_RE.search(t) and not APPLY_RE.search(t) and t != title), ""
    )
    return title, provided


def looks_like_login_page(html: str) -> bool:
    """로그인이 필요하다는 그누보드 안내 화면인지. 리뷰플레이스는 비로그인 접근을 200 + alert 로 돌려준다."""
    html = html or ""
    return "회원만 접근" in html or 'name="mb_password"' in html


def parse_campaigns(html: str, today: date) -> list[Campaign]:
    """선정 목록 HTML → Campaign 목록. 같은 캠페인이 여러 링크로 있어도 한 번만 담는다."""
    soup = BeautifulSoup(html, "html.parser")
    campaigns: list[Campaign] = []
    seen: set[str] = set()
    for anchor in soup.select('a[href*="/pr/?id="]'):
        href = anchor.get("href") or ""
        found = LINK_RE.search(href)
        if not found:
            continue
        campaign_id = found.group(1)
        if campaign_id in seen:
            continue
        seen.add(campaign_id)
        card = _card_for(anchor)
        title, _provided = _title_and_provided(card)
        left = days_left(_norm(card.get_text(" ")))
        campaigns.append(
            Campaign(
                site=KEY,
                campaign_id=campaign_id,
                title=title or f"{NAME} #{campaign_id}",
                status=Status.SELECTED,
                kind=next((k for k in KINDS if k in title), None),
                selected_at=today,
                review_deadline=today + timedelta(days=left) if left is not None else None,
                url=ORIGIN + _path(href),
                site_name=NAME,
            )
        )
    return campaigns


class ReviewplaceCollector(Collector):
    key = KEY
    name = NAME
    origin = ORIGIN
    login_path = "/bbs/login.php"
    login_check_path = "/bbs/login_check.php"
    list_path = "/my/cmp_select.php"

    def _collect(self, client: httpx.Client, today: date) -> list[Campaign]:
        self._login(client)
        page = self._get(client, self.list_path)
        if looks_like_login_page(page.text):
            raise LoginError(f"{NAME} 로그인에 실패했습니다. Secrets 의 아이디·비밀번호를 확인해 주세요.")
        return parse_campaigns(page.text, today)

    def _get(self, client: httpx.Client, path: str) -> httpx.Response:
        try:
            return client.get(path)
        except httpx.HTTPError as e:
            raise CollectError(f"{NAME} 접속 실패 ({type(e).__name__})") from None

    def _login(self, client: httpx.Client) -> None:
        self._get(client, self.login_path)  # 세션 쿠키(PHPSESSID)를 먼저 받아 둔다
        try:
            client.post(
                self.login_check_path,
                data={
                    "mb_id": self._id,
                    "mb_password": self._password,
                    "url": self.list_path,
                    "auto_login": "1",
                },
            )
        except httpx.HTTPError as e:
            raise CollectError(f"{NAME} 로그인 요청 실패 ({type(e).__name__})") from None
        # 로그인 성패는 응답 본문으로 판별하지 않는다(그누보드는 성공·실패 모두 스크립트로 이동을 지시한다).
        # 바로 이어서 읽는 선정 목록이 로그인 안내 화면이면 실패로 본다.
