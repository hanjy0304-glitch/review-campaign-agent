"""디너의여왕(dinnerqueen.net) 서버 수집기.

- 로그인: `/login/form_new` 폼 → `POST /login/proc` (email, passwd, gubun=login, snstype=0).
  응답은 JSON 이고 `code` 가 200 이면 성공이다(2026-11-09 공개 페이지의 login.js 로 확인).
- 선정 목록: `/mypage/widget` ('나의캠페인' 위젯). 로그인하지 않으면 메인(`/`)으로 리다이렉트된다.
- 파싱 기준은 크롬 확장(`extension/src/dinnerqueen_parse.js`)과 같다. 상세 링크(`/taste/번호`)와
  'N일 남음'·'오늘까지' 같은 마감 문구로 카드를 찾는다.
- 2026-11-09 확인: 계정 없이 로그인해 보면 `{"code":404,"msg":"No UserInfo"}` 가 돌아온다(로그인 경로 실측).
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from ..models import Campaign, Status
from .base import CollectError, Collector, LoginError
from .common import DDAY_RE, card_for, days_left, norm, normalize_kind, site_path

KEY = "dinnerqueen"
NAME = "디너의여왕"
ORIGIN = "https://dinnerqueen.net"

LOGIN_PATH = "/login/form_new"
LOGIN_PROC_PATH = "/login/proc"
LIST_PATH = "/mypage/widget"

LINK_SELECTOR = 'a[href*="/taste/"]'
LINK_RE = re.compile(r"/taste/(\d+)")
APPLY_SUFFIX_RE = re.compile(r"\s*신청하기$")


def _title_of(card, anchor, paragraphs: list[str]) -> str:
    """제목: 카드 이미지의 alt. 없으면 제목 문단, 마지막으로 링크 title 에서 '신청하기' 꼬리를 뗀 값.

    메인 배너처럼 이미지 alt 가 이미지 주소인 경우는 카드가 아니므로 건너뛴다.
    """
    for img in card.select("img[alt]"):
        alt = norm(img.get("alt", ""))
        if alt and not alt.startswith("http"):
            return alt
    for text in paragraphs:
        if text and not DDAY_RE.search(text) and not re.search(r"신청\s*\d+", text) and len(text) > 1:
            return text
    return APPLY_SUFFIX_RE.sub("", norm(anchor.get("title", "")))


def parse_campaigns(html: str, today: date) -> list[Campaign]:
    """마이페이지 HTML → Campaign 목록. 같은 캠페인이 여러 링크로 있어도 한 번만 담는다."""
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
        text = norm(card.get_text(" "))
        paragraphs = [norm(p.get_text(" ")) for p in card.select("p")]
        # 카드가 아니라 배너·버튼 링크인 경우를 거른다 (마감 문구도, 문단도 없음).
        if not DDAY_RE.search(text) and not paragraphs:
            continue
        title = _title_of(card, anchor, paragraphs)
        badge = card.select_one("[class*=badge]")
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
                url=ORIGIN + site_path(anchor.get("href") or f"/taste/{campaign_id}"),
                site_name=NAME,
            )
        )
    return campaigns


class DinnerqueenCollector(Collector):
    key = KEY
    name = NAME
    origin = ORIGIN
    login_path = LOGIN_PATH
    login_proc_path = LOGIN_PROC_PATH
    list_path = LIST_PATH

    def _collect(self, client: httpx.Client, today: date) -> list[Campaign]:
        self._login(client)
        page = self._get(client, self.list_path)
        if urlsplit(str(page.url)).path in ("/", ""):
            raise LoginError(f"{NAME} 로그인에 실패했습니다. Secrets 의 이메일·비밀번호를 확인해 주세요.")
        return parse_campaigns(page.text, today)

    def _get(self, client: httpx.Client, path: str) -> httpx.Response:
        try:
            return client.get(path)
        except httpx.HTTPError as e:
            raise CollectError(f"{NAME} 접속 실패 ({type(e).__name__})") from None

    def _login(self, client: httpx.Client) -> None:
        self._get(client, self.login_path)  # 세션 쿠키(dq_sessions)를 먼저 받아 둔다
        try:
            response = client.post(
                self.login_proc_path,
                data={
                    "redirectUrl": ORIGIN + "/",
                    "type": "email",
                    "gubun": "login",
                    "email": self._id,
                    "passwd": self._password,
                    "auto_login": "on",
                    "snstype": "0",
                },
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
        except httpx.HTTPError as e:
            raise CollectError(f"{NAME} 로그인 요청 실패 ({type(e).__name__})") from None
        try:
            code = (response.json() or {}).get("code")
        except ValueError:
            raise CollectError(f"{NAME} 로그인 응답을 읽지 못했습니다.") from None
        if code != 200:
            # 500 비밀번호 불일치 / 404 가입 이력 없음 / 600·700 탈퇴 계정
            raise LoginError(f"{NAME} 로그인에 실패했습니다 (응답 코드 {code}). Secrets 의 이메일·비밀번호를 확인해 주세요.")


__all__ = [
    "KEY",
    "LIST_PATH",
    "NAME",
    "ORIGIN",
    "DinnerqueenCollector",
    "parse_campaigns",
]
