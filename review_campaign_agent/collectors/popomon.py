"""포포몬(popomon.com) 서버 수집기.

- 로그인: NextAuth(사이트 앱의 로그인 방식) — `/next/api/auth/csrf` 토큰을 받아
  `POST /next/api/auth/callback/Credentials` (username, password) 로 세션 쿠키를 받는다.
  성공 여부는 `/next/api/auth/session` 이 사용자 정보를 돌려주는지로 확인한다.
- 선정 목록: `GET /api_p/myCampaign/fetch_getContents?state=choice&pageNum=0` 의 JSON.
  응답은 `{"code":200,"data":{"contentsData1":[{"C_idx","C_title","CV_c_end_date",...}]}}` 형태이고,
  `pageNum` 을 올리면 다음 묶음이 온다(한 묶음 6건 기준으로 화면이 '더 보기'를 판단한다).
- 필드 이름과 로그인 경로는 2026-11-09 사이트의 공개 화면·프런트엔드 코드에서 확인했다.
  다만 **로그인한 뒤의 실제 응답은 아직 확인하지 못했다** (계정 정보가 없어 확인할 수 없다).
  그래서 응답 형태가 조금 달라도 읽히도록, 카드에 해당하는 항목에서 번호·제목·마감일을 찾는 방식으로 쓴다.
"""

from __future__ import annotations

import re
from datetime import date

import httpx

from ..models import Campaign, Status
from .base import CollectError, Collector, LoginError
from .common import norm, normalize_kind

KEY = "popomon"
NAME = "포포몬"
ORIGIN = "https://popomon.com"

CSRF_PATH = "/next/api/auth/csrf"
CALLBACK_PATH = "/next/api/auth/callback/Credentials"
SESSION_PATH = "/next/api/auth/session"
LIST_PATH = "/api_p/myCampaign/fetch_getContents"
DETAIL_PATH = "/next/campaign/"

# 선정(state=choice) 캠페인만 받는다. 신청만 한 캠페인까지 표에 들어오지 않게 하기 위해서다.
LIST_STATE = "choice"
PAGE_HINT = 6  # 화면이 '더 보기'를 판단하는 한 묶음 크기
MAX_PAGES = 20

DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
RECRUIT_KINDS = {"visiting": "방문형", "shipping": "배송형"}


def _to_date(value) -> date | None:
    """'2026-11-15' 또는 '2026-11-15 23:59:59' → date. 비어 있거나 0000-00-00 이면 None."""
    m = DATE_RE.match(str(value or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _items(payload: dict) -> list[dict]:
    """응답에서 캠페인 항목 목록을 꺼낸다 (data.contentsData1 → 없으면 data 자체가 목록인 경우)."""
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("contentsData1", "contentsData", "list"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def parse_campaigns(payload: dict, today: date) -> list[Campaign]:
    """선정 목록 JSON → Campaign 목록. 같은 캠페인이 두 번 와도 한 번만 담는다."""
    campaigns: list[Campaign] = []
    seen: set[str] = set()
    for item in _items(payload):
        campaign_id = str(item.get("C_idx") or item.get("campaignIdx") or "").strip()
        if not campaign_id or campaign_id in seen:
            continue
        seen.add(campaign_id)

        title = norm(str(item.get("C_title") or item.get("title") or ""))
        # 제출(리뷰) 마감일. 없으면 광고주가 정한 제출 마감(CV_request_deadline)을 쓴다.
        deadline = _to_date(item.get("CV_c_end_date")) or _to_date(item.get("CV_request_deadline"))
        recruit_type = str(item.get("C_recruit_type") or "")
        kind = RECRUIT_KINDS.get(recruit_type) or normalize_kind(recruit_type) or normalize_kind(title)

        campaigns.append(
            Campaign(
                site=KEY,
                campaign_id=campaign_id,
                title=title or f"{NAME} #{campaign_id}",
                status=Status.SELECTED,
                kind=kind,
                selected_at=today,
                review_deadline=deadline,
                url=ORIGIN + DETAIL_PATH + campaign_id,
                site_name=NAME,
            )
        )
    return campaigns


class PopomonCollector(Collector):
    key = KEY
    name = NAME
    origin = ORIGIN
    csrf_path = CSRF_PATH
    callback_path = CALLBACK_PATH
    session_path = SESSION_PATH
    list_path = LIST_PATH

    def _collect(self, client: httpx.Client, today: date) -> list[Campaign]:
        self._login(client)
        items: list[dict] = []
        for page in range(MAX_PAGES):
            chunk = self._fetch_page(client, page)
            items.extend(chunk)
            if len(chunk) < PAGE_HINT:
                break
        # 묶음 경계에서 같은 캠페인이 겹칠 수 있어 parse_campaigns 가 번호 기준으로 한 번 더 정리한다.
        return parse_campaigns({"data": {"contentsData1": items}}, today)

    def _fetch_page(self, client: httpx.Client, page: int) -> list[dict]:
        try:
            response = client.get(self.list_path, params={"state": LIST_STATE, "pageNum": page})
        except httpx.HTTPError as e:
            raise CollectError(f"{NAME} 접속 실패 ({type(e).__name__})") from None
        if response.status_code in (401, 403):
            raise LoginError(f"{NAME} 로그인에 실패했습니다. Secrets 의 아이디·비밀번호를 확인해 주세요.")
        try:
            payload = response.json()
        except ValueError:
            raise CollectError(f"{NAME} 목록 응답을 읽지 못했습니다 (로그인 실패 또는 사이트 화면 변경).") from None
        if not isinstance(payload, dict):
            raise CollectError(f"{NAME} 목록 응답 형식이 바뀌었습니다.")
        code = payload.get("code")
        if code in (401, 403):
            raise LoginError(f"{NAME} 로그인에 실패했습니다. Secrets 의 아이디·비밀번호를 확인해 주세요.")
        if payload.get("success") is False or (code is not None and code != 200):
            raise CollectError(f"{NAME} 목록을 받지 못했습니다 (응답 코드 {code}).")
        return _items(payload)

    def _login(self, client: httpx.Client) -> None:
        try:
            csrf = client.get(self.csrf_path)
            token = (csrf.json() or {}).get("csrfToken")
            if not token:
                raise CollectError(f"{NAME} 로그인 준비에 실패했습니다.")
            response = client.post(
                self.callback_path,
                data={
                    "csrfToken": token,
                    "username": self._id,
                    "password": self._password,
                    "callbackUrl": ORIGIN + "/next/mypage",
                    "json": "true",
                },
            )
            session = client.get(self.session_path)
        except httpx.HTTPError as e:
            raise CollectError(f"{NAME} 로그인 요청 실패 ({type(e).__name__})") from None
        except ValueError:
            raise CollectError(f"{NAME} 로그인 응답을 읽지 못했습니다.") from None
        if response.status_code >= 400 or not self._has_user(session):
            raise LoginError(f"{NAME} 로그인에 실패했습니다. Secrets 의 아이디·비밀번호를 확인해 주세요.")

    @staticmethod
    def _has_user(response: httpx.Response) -> bool:
        """로그인 세션 확인. 로그인 전에는 `{}` 가, 로그인 뒤에는 사용자 정보가 돌아온다."""
        try:
            payload = response.json()
        except ValueError:
            return False
        return isinstance(payload, dict) and bool(payload.get("user") or payload.get("expires"))


__all__ = [
    "KEY",
    "LIST_PATH",
    "NAME",
    "ORIGIN",
    "PopomonCollector",
    "parse_campaigns",
]
