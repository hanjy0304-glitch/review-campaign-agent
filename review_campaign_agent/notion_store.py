import re
import time
from collections.abc import Callable
from datetime import date

import httpx

from . import notion_schema as ns
from .models import Campaign, Status

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
RETRY_STATUS = {429, 500, 502, 503, 504}


class NotionError(Exception):
    pass


def parse_notion_id(url_or_id: str) -> str:
    """Notion 페이지 링크 또는 id 에서 32자리 id 를 뽑아 UUID 형식으로 돌려준다."""
    path = url_or_id.strip().split("?")[0].split("#")[0]
    # "제목-<32자리>" 형태라서 제목 끝 글자(a-f)가 id 에 섞이지 않도록 하이픈을 지우기 전에 경계를 본다
    plain = re.findall(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])", path)
    dashed = re.findall(r"(?<![0-9a-fA-F])[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}(?![0-9a-fA-F])", path)
    found = plain[-1] if plain else dashed[-1].replace("-", "") if dashed else None
    if not found:
        raise NotionError("Notion 링크에서 페이지 id 를 찾지 못했습니다. 페이지의 '링크 복사' 주소를 넣으세요.")
    h = found.lower()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


class NotionClient:
    def __init__(
        self,
        token: str,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        retries: int = 3,
    ):
        self._headers = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION}
        self._client = client or httpx.Client(base_url=API, timeout=30)
        self._sleep = sleep
        self._retries = retries

    def request(self, method: str, path: str, json: dict | None = None) -> dict:
        for attempt in range(self._retries):
            try:
                resp = self._client.request(method, path, json=json, headers=self._headers)
            except httpx.HTTPError as e:  # 오류 메시지에 요청 헤더(토큰)가 섞이지 않도록 종류만 남긴다
                raise NotionError(f"Notion 연결 실패: {type(e).__name__}") from None
            if resp.status_code in RETRY_STATUS and attempt < self._retries - 1:
                self._sleep(float(resp.headers.get("Retry-After", 1)))
                continue
            if resp.status_code >= 400:
                try:
                    message = resp.json().get("message", "")
                except ValueError:
                    message = ""
                raise NotionError(f"Notion API 오류 {resp.status_code}: {message}")
            return resp.json()
        raise NotionError("Notion API 재시도 초과")  # pragma: no cover


def create_database(api: NotionClient, parent_page_id: str, site_names: list[str], title: str = "체험단 관리") -> dict:
    """빈 페이지 아래에 체험단 관리 DB 를 만든다. {'id': ..., 'url': ...} 반환."""
    data = api.request(
        "POST",
        "/databases",
        {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": ns.database_properties(site_names),
        },
    )
    return {"id": data["id"], "url": data.get("url", "")}


# --- 속성 읽기/쓰기 도우미 ---------------------------------------------------

def _text(prop: dict | None) -> str:
    if not prop:
        return ""
    parts = prop.get("title") or prop.get("rich_text") or []
    return "".join(p.get("plain_text", "") for p in parts)


def _select(prop: dict | None) -> str:
    return ((prop or {}).get("select") or {}).get("name", "")


def _date(prop: dict | None) -> date | None:
    start = ((prop or {}).get("date") or {}).get("start")
    return date.fromisoformat(start[:10]) if start else None


def _w_text(kind: str, value: str) -> dict:
    return {kind: [{"type": "text", "text": {"content": value}}] if value else []}


def _w_select(value: str) -> dict:
    return {"select": {"name": value} if value else None}


def _w_date(value: date | None) -> dict:
    return {"date": {"start": value.isoformat()} if value else None}


def _selection_name(status: Status) -> str:
    """진행 단계(VISITED/DONE)는 사람이 관리하므로 선정상태로는 모두 '선정'이다."""
    return {Status.APPLIED: ns.APPLIED_STATE, Status.REJECTED: ns.REJECTED_STATE}.get(status, ns.SELECTED_STATE)


def page_to_campaign(page: dict) -> Campaign:
    p = page["properties"]
    unique_key = _text(p.get(ns.KEY))
    site, _, campaign_id = unique_key.partition(":") if ":" in unique_key else ("manual", "", page["id"])
    stage = _select(p.get(ns.STAGE)) or ns.STAGE_NEED
    selection = _select(p.get(ns.SELECTION)) or ns.SELECTED_STATE  # 수동 입력 행은 선정상태가 비어 있다
    if selection == ns.REJECTED_STATE:
        status = Status.REJECTED
    elif selection == ns.APPLIED_STATE:
        status = Status.APPLIED
    elif stage == ns.STAGE_DONE:
        status = Status.DONE
    elif stage == ns.STAGE_VISITED:
        status = Status.VISITED
    else:
        status = Status.SELECTED
    days = (p.get(ns.DAYS_LEFT) or {}).get("number")
    return Campaign(
        site=site,
        campaign_id=campaign_id,
        title=_text(p.get(ns.TITLE)),
        status=status,
        kind=_select(p.get(ns.KIND)) or None,
        selected_at=_date(p.get(ns.SELECTED_AT)),
        visit_date=_date(p.get(ns.VISIT)),
        review_deadline=_date(p.get(ns.DEADLINE)),
        url=(p.get(ns.URL) or {}).get("url") or page.get("url", ""),
        notified={k for k in _text(p.get(ns.NOTIFIED)).split(",") if k},
        site_name=_select(p.get(ns.SITE)),
        ref=page["id"],
        shown_days_left=int(days) if days is not None else None,
    )


def campaign_to_properties(c: Campaign) -> dict:
    """어댑터가 수집한 체험단 → 새 행 속성. 사람 칸(진행단계 등)은 비워 둔다."""
    selection = _selection_name(c.status)
    props = {
        ns.TITLE: _w_text("title", c.title),
        ns.SITE: _w_select(c.site_name or c.site),
        ns.SELECTION: _w_select(selection),
        ns.SELECTED_AT: _w_date(c.selected_at),
        ns.DEADLINE: _w_date(c.review_deadline),
        ns.URL: {"url": c.url or None},
        ns.SOURCE: _w_select(ns.SOURCE_AUTO),
        ns.KEY: _w_text("rich_text", c.key),
    }
    if c.kind:
        props[ns.KIND] = _w_select(c.kind)
    if c.visit_date:
        props[ns.VISIT] = _w_date(c.visit_date)
    return props


class NotionStore:
    def __init__(self, api: NotionClient, database_id: str):
        self._api = api
        self._db = database_id

    def fetch_rows(self) -> list[Campaign]:
        """작성 완료가 아닌 행만 읽는다 (알림 대상은 모두 여기에 있다)."""
        body: dict = {
            "page_size": 100,
            "filter": {
                "or": [
                    {"property": ns.STAGE, "select": {"is_empty": True}},
                    {"property": ns.STAGE, "select": {"does_not_equal": ns.STAGE_DONE}},
                ]
            },
        }
        rows: list[Campaign] = []
        while True:
            data = self._api.request("POST", f"/databases/{self._db}/query", body)
            for p in data["results"]:
                c = page_to_campaign(p)
                if c.is_test:
                    try:
                        self._api.request("PATCH", f"/pages/{c.ref}", {"archived": True})
                    except Exception:
                        pass
                    continue
                rows.append(c)
            if not data.get("has_more"):
                return rows
            body["start_cursor"] = data["next_cursor"]

    def mark_notified(self, c: Campaign) -> None:
        self._api.request(
            "PATCH", f"/pages/{c.ref}", {"properties": {ns.NOTIFIED: _w_text("rich_text", ",".join(sorted(c.notified)))}}
        )

    def set_days_left(self, c: Campaign, days_left: int | None) -> None:
        self._api.request("PATCH", f"/pages/{c.ref}", {"properties": {ns.DAYS_LEFT: {"number": days_left}}})
        c.shown_days_left = days_left

    def upsert_collected(self, collected: list[Campaign], rows: list[Campaign]) -> tuple[int, int]:
        """어댑터가 수집한 체험단을 반영한다. 새 건은 행 추가, 기존 건은 에이전트 칸만 갱신. (추가 수, 갱신 수)"""
        by_key = {r.key: r for r in rows if r.site != "manual"}
        added = updated = 0
        for c in collected:
            row = by_key.get(c.key)
            if row is None:
                self._api.request(
                    "POST", "/pages", {"parent": {"database_id": self._db}, "properties": campaign_to_properties(c)}
                )
                added += 1
                continue
            changes = {}
            if _selection_name(c.status) != _selection_name(row.status):
                changes[ns.SELECTION] = _w_select(_selection_name(c.status))
            if c.review_deadline and c.review_deadline != row.review_deadline:
                changes[ns.DEADLINE] = _w_date(c.review_deadline)
            if changes:
                self._api.request("PATCH", f"/pages/{row.ref}", {"properties": changes})
                updated += 1
        return added, updated
