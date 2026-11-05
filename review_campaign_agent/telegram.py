from datetime import date

import httpx

from .models import Campaign, Status
from .rules import Notification

API = "https://api.telegram.org"


class NotifyError(Exception):
    pass


def _bot_request(client: httpx.Client, token: str, method: str, payload: dict | None = None) -> dict:
    """토큰이 URL 에 들어가므로 오류에는 URL 을 절대 싣지 않는다."""
    try:
        resp = client.post(f"{API}/bot{token}/{method}", json=payload or {})
    except httpx.HTTPError as e:
        raise NotifyError(f"텔레그램 연결 실패: {type(e).__name__}") from None
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400 or not data.get("ok", False):
        raise NotifyError(f"텔레그램 오류 {resp.status_code}: {data.get('description', '')}")
    return data


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, client: httpx.Client | None = None):
        self._token = token
        self._chat_id = chat_id
        self._client = client or httpx.Client(timeout=30)

    def send(self, text: str) -> None:
        _bot_request(
            self._client, self._token, "sendMessage",
            {"chat_id": self._chat_id, "text": text, "disable_web_page_preview": True},
        )


def get_bot_info(token: str, client: httpx.Client | None = None) -> dict:
    """봇의 공개 정보(username 등)를 확인한다."""
    return _bot_request(client or httpx.Client(timeout=30), token, "getMe").get("result", {})


def find_chat_id(token: str, client: httpx.Client | None = None) -> str | None:
    """봇에게 아무 메시지나 보낸 뒤 호출하면 그 대화의 chat_id 를 돌려준다."""
    data = _bot_request(client or httpx.Client(timeout=30), token, "getUpdates")
    for update in reversed(data.get("result", [])):
        chat = (update.get("message") or update.get("channel_post") or {}).get("chat")
        if chat:
            return str(chat["id"])
    return None


def _d(day: date | None) -> str:
    return f"{day.month}/{day.day}" if day else "미정"


def _when(days: int) -> str:
    return "오늘" if days == 0 else f"D-{days}"


def _title(c: Campaign) -> str:
    return f"{c.title} ({c.site_name or c.site})"


def _tail(c: Campaign) -> str:
    return f"\n{c.url}" if c.url else ""


def format_notification(n: Notification) -> str:
    c = n.campaign
    if n.kind == "new_selection":
        if c.review_deadline is None:
            deadline = "글 마감일: 아직 몰라요. Notion에 입력해 주세요"
        elif n.days_left is not None and n.days_left < 0:
            deadline = f"글 마감일 {_d(c.review_deadline)} (이미 지났어요)"
        else:
            deadline = f"글 마감일 {_d(c.review_deadline)}" + (f" ({_when(n.days_left)})" if n.days_left is not None else "")
        visit = f"\n방문일 {_d(c.visit_date)}" if c.visit_date else ""
        return f"🎉 선정됐어요\n{_title(c)}\n{deadline}{visit}{_tail(c)}"
    if n.kind == "deadline":
        head = "⏰ 글 마감 오늘!" if n.days_left == 0 else f"⏰ 글 마감 {_when(n.days_left or 0)}"
        return f"{head}\n{_title(c)}\n마감 {_d(c.review_deadline)}{_tail(c)}"
    if n.kind == "check_done":
        return (
            f"⚠️ 글 마감이 지났어요 ({-(n.days_left or 0)}일 전)\n{_title(c)}\n마감 {_d(c.review_deadline)}{_tail(c)}\n"
            "이 체험단 마감됐나요? 완료됐으면 Notion 진행단계를 '작성완료'로 바꿔 주세요 — 바꾸면 알림에서 빠져요"
        )
    if n.kind == "deadline_missing":
        return f"❓ 글 마감일을 입력해 주세요\n{_title(c)}{_tail(c)}"
    if n.kind == "visit":
        head = "📍 방문 오늘!" if n.days_left == 0 else f"📍 방문 {_when(n.days_left or 0)}"
        return f"{head}\n{_title(c)}\n방문일 {_d(c.visit_date)}{_tail(c)}"
    if n.kind == "visit_missing":
        return f"📅 방문일을 입력해 주세요 (예약하셨나요?)\n{_title(c)}{_tail(c)}"
    raise ValueError(f"알 수 없는 알림 종류: {n.kind}")


def format_summary(campaigns: list[Campaign], today: date) -> str | None:
    """아직 글을 쓰지 않은 선정 건을 마감 임박 순으로. 기간이 지난 건은 종료 처리하지 않고
    완료 확인을 요청하는 칸으로 옮긴다(사람이 진행단계를 바꿔야 목록에서 빠진다). 할 일이 하나도 없으면 None."""
    todo = [c for c in campaigns if not c.is_test and c.status in (Status.SELECTED, Status.VISITED)]
    if not todo:
        return None
    open_items = [c for c in todo if c.review_deadline is None or c.review_deadline >= today]
    overdue = [c for c in todo if c.review_deadline is not None and c.review_deadline < today]
    lines = []
    if open_items:
        open_items.sort(key=lambda c: (c.review_deadline is None, c.review_deadline or today))
        lines.append(f"📋 오늘의 체험단 ({len(open_items)}건)")
        for c in open_items:
            if c.review_deadline is None:
                when = "마감일 미정"
            else:
                when = f"마감 {_d(c.review_deadline)} ({_when((c.review_deadline - today).days)})"
            visit = f" · 방문 {_d(c.visit_date)}" if c.visit_date and c.status == Status.SELECTED else ""
            lines.append(f"• {_title(c)} — {when}{visit}")
    if overdue:
        overdue.sort(key=lambda c: c.review_deadline)
        if lines:
            lines.append("")
        lines.append(
            f"☑️ 기간이 지난 체험단 ({len(overdue)}건) — 마감됐나요? "
            "완료됐으면 진행단계를 '작성완료'로 바꿔 주세요 (바꾸면 이 목록에서 빠져요)"
        )
        for c in overdue:
            lines.append(f"• {_title(c)} — 마감 {_d(c.review_deadline)} 지남")
    return "\n".join(lines)
