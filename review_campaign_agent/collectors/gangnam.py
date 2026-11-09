"""강남맛집(강남맛집.net, punycode xn--939au0g4vj8sq.net) 서버 수집기.

- 로그인: `/bbs/login.php` 폼 → `/bbs/login_check.php` (그누보드: mb_id, mb_password, url, auto_login)
- 선정 목록: `/theme/go/mypage/` ('나의 캠페인')
- 파싱 기준은 크롬 확장(`extension/src/gangnam_parse.js`)과 같다. 상세 링크(`/cp/?id=번호`)와
  '24일 남음'·'D-n'·'11.11 까지' 같은 마감 문구로 카드를 찾고, 링크 없이 `data-product` 로만
  표시된 카드도 읽는다.
- 주의: `gangnam-review.net` 은 이 주소로 301 리다이렉트된다. 리다이렉트 뒤 주소를 써야 한다.
- 미검증(2026-11-09): 이 저장소를 만든 환경에서는 강남맛집에 접속이 되지 않아(연결 시간 초과)
  로그인 화면·마이페이지를 직접 열어보지 못했다. 로그인 폼 필드와 카드 구조는 `config/sites.yaml` 과
  확장 파서에 기록된 공개 페이지 관찰 결과를 따른다.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import httpx
from bs4 import BeautifulSoup

from ..models import Campaign, Status
from .base import CollectError, Collector, LoginError
from .common import APPLY_RE, DDAY_RE, card_for, days_left, norm, normalize_kind, site_path

KEY = "gangnam"
NAME = "강남맛집"
ORIGIN = "https://xn--939au0g4vj8sq.net"

LOGIN_PATH = "/bbs/login.php"
LOGIN_CHECK_PATH = "/bbs/login_check.php"
LIST_PATH = "/theme/go/mypage/"

LINK_SELECTOR = 'a[href*="/cp/?id="]'
LINK_RE = re.compile(r"[?&]id=(\d+)")
GATE_TEXT = "로그인 한 회원만 접근"


def looks_like_login_page(html: str) -> bool:
    """로그인이 필요하다는 안내 화면인지. 강남맛집은 비로그인 접근을 alert + 로그인 화면으로 돌려준다."""
    html = html or ""
    return GATE_TEXT in html or 'name="mb_password"' in html


def _pick_title(card) -> str:
    named = card.select_one("dt.tit, .tit, dt.tit a")
    if named and norm(named.get_text(" ")):
        return norm(named.get_text(" "))
    # 제목 클래스가 없으면: 마감·신청수 문구가 아닌 글을 가진 첫 캠페인 링크(또는 이미지 alt).
    for anchor in card.select(LINK_SELECTOR):
        text = norm(anchor.get_text(" "))
        if text and not DDAY_RE.search(text) and not APPLY_RE.search(text):
            return text
    img = card.select_one("img[alt]")
    return norm(img.get("alt", "")) if img else ""


def parse_campaigns(html: str, today: date) -> list[Campaign]:
    """마이페이지 HTML → Campaign 목록. 같은 캠페인이 여러 링크로 있어도 한 번만 담는다."""
    soup = BeautifulSoup(html, "html.parser")
    cards: dict[str, object] = {}
    for anchor in soup.select(LINK_SELECTOR):
        found = LINK_RE.search(anchor.get("href") or "")
        if not found:
            continue
        campaign_id = found.group(1)
        if campaign_id not in cards:
            cards[campaign_id] = card_for(anchor, LINK_SELECTOR, LINK_RE)
    # 링크 없이 data-product 로만 표시된 카드(스크립트로 이동하는 화면)도 읽는다.
    for li in soup.select("li[data-product]"):
        campaign_id = norm(li.get("data-product", ""))
        if campaign_id.isdigit() and campaign_id not in cards:
            cards[campaign_id] = li

    campaigns: list[Campaign] = []
    for campaign_id, card in cards.items():
        text = norm(card.get_text(" "))
        title = _pick_title(card)
        if not title and not text:
            continue
        badge = card.select_one("em.type, .type")
        left = days_left(text, today)
        campaigns.append(
            Campaign(
                site=KEY,
                campaign_id=campaign_id,
                title=title or f"{NAME} #{campaign_id}",
                status=Status.SELECTED,
                kind=normalize_kind(badge.get_text(" ") if badge else "") or normalize_kind(text),
                selected_at=today,
                review_deadline=today + timedelta(days=left) if left is not None else None,
                url=ORIGIN + site_path(f"/cp/?id={campaign_id}"),
                site_name=NAME,
            )
        )
    return campaigns


class GangnamCollector(Collector):
    key = KEY
    name = NAME
    origin = ORIGIN
    login_path = LOGIN_PATH
    login_check_path = LOGIN_CHECK_PATH
    list_path = LIST_PATH

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
        self._get(client, self.login_path)  # 세션 쿠키를 먼저 받아 둔다
        try:
            client.post(
                self.login_check_path,
                data={
                    "url": ORIGIN + self.list_path,
                    "mb_id": self._id,
                    "mb_password": self._password,
                    "auto_login": "1",
                },
            )
        except httpx.HTTPError as e:
            raise CollectError(f"{NAME} 로그인 요청 실패 ({type(e).__name__})") from None
        # 로그인 성패는 응답 본문으로 판별하지 않는다. 이어서 읽는 마이페이지가 로그인 안내 화면이면 실패로 본다.


__all__ = [
    "KEY",
    "LIST_PATH",
    "NAME",
    "ORIGIN",
    "GangnamCollector",
    "looks_like_login_page",
    "parse_campaigns",
]
