"""서울오빠(seoulouba.co.kr) 서버 수집기.

- 로그인: `/bbs/login.php` 폼 → `/bbs/login_check.php` (그누보드: mb_id, mb_password, url, auto_login)
- 선정 목록: `/mypage/my_campaign.php` ('내 캠페인')
- 파싱 기준은 크롬 확장(`extension/src/seoulouba_parse.js`)과 같다. 클래스 이름 대신
  상세 링크(`/campaign/?c=번호`)와 'D-n'·'D-day'·'오늘까지' 같은 마감 문구로 카드를 찾는다.
- 2026-11-09 확인: 로그인 전에 마이페이지를 열면 "로그인 하십시오." 안내가 나온다(계정 정보 없이 확인).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import httpx
from bs4 import BeautifulSoup

from ..models import Campaign, Status
from .base import CollectError, Collector, LoginError
from .common import DDAY_RE, card_for, days_left, norm, normalize_kind, site_path

KEY = "seoulouba"
NAME = "서울오빠"
ORIGIN = "https://seoulouba.co.kr"

LOGIN_PATH = "/bbs/login.php"
LOGIN_CHECK_PATH = "/bbs/login_check.php"
LIST_PATH = "/mypage/my_campaign.php"

LINK_SELECTOR = 'a[href*="/campaign/?c="]'
LINK_RE = re.compile(r"[?&]c=(\d+)")
GATE_TEXT = "로그인 하십시오"


def looks_like_login_page(html: str) -> bool:
    """로그인이 필요하다는 안내 화면인지. 서울오빠는 비로그인 접근을 200 + 안내 문구로 돌려준다."""
    html = html or ""
    return GATE_TEXT in html or 'name="mb_password"' in html


def parse_campaigns(html: str, today: date) -> list[Campaign]:
    """'내 캠페인' HTML → Campaign 목록. 카드 하나에 링크가 여러 개여도 한 번만 담는다."""
    soup = BeautifulSoup(html, "html.parser")
    campaigns: list[Campaign] = []
    seen: set[str] = set()
    for anchor in soup.select(LINK_SELECTOR):
        found = LINK_RE.search(anchor.get("href") or "")
        if not found:
            continue
        campaign_id = found.group(1)
        if campaign_id in seen:
            continue
        seen.add(campaign_id)

        card = card_for(anchor, LINK_SELECTOR, LINK_RE)
        title_el = card.select_one(".t_ttl strong, .t_ttl")
        title = norm(title_el.get_text(" ")) if title_el else ""
        if not title:
            title = norm(anchor.get_text(" "))
        provided_el = card.select_one(".t_basic")
        badge = card.select_one(".icon_tag")
        text = norm(card.get_text(" "))
        # 카드가 아니라 배너·버튼 링크인 경우를 거른다 (제목·유형·마감 문구가 모두 없음).
        if not (title_el or provided_el or badge or DDAY_RE.search(text)):
            continue
        left = days_left(text, today)

        campaigns.append(
            Campaign(
                site=KEY,
                campaign_id=campaign_id,
                title=title or f"{NAME} #{campaign_id}",
                status=Status.SELECTED,
                kind=normalize_kind(badge.get_text(" ") if badge else "") or normalize_kind(title),
                selected_at=today,
                review_deadline=today + timedelta(days=left) if left is not None else None,
                url=ORIGIN + site_path(anchor.get("href") or f"/campaign/?c={campaign_id}"),
                site_name=NAME,
            )
        )
    return campaigns


class SeouloubaCollector(Collector):
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
        self._get(client, self.login_path)  # 세션 쿠키(PHPSESSID)를 먼저 받아 둔다
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
        # 로그인 성패는 응답 본문으로 판별하지 않는다(그누보드는 성공·실패 모두 스크립트로 이동을 지시한다).
        # 바로 이어서 읽는 '내 캠페인'이 로그인 안내 화면이면 실패로 본다.


__all__ = [
    "KEY",
    "LIST_PATH",
    "NAME",
    "ORIGIN",
    "SeouloubaCollector",
    "days_left",
    "looks_like_login_page",
    "parse_campaigns",
]
