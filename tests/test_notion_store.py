import json
from datetime import date

import httpx
import pytest

from review_campaign_agent import notion_schema as ns
from review_campaign_agent.models import Campaign, Status
from review_campaign_agent.notion_store import (
    NotionClient,
    NotionError,
    NotionStore,
    create_database,
    page_to_campaign,
    parse_notion_id,
)

DB = "db-id"
SAMPLE_ID = "0123456789abcdef0123456789abcdef"


def txt(kind, value):
    return {kind: [{"plain_text": value}]} if value else {kind: []}


def sel(name):
    return {"select": {"name": name} if name else None}


def dt(d):
    return {"date": {"start": d} if d else None}


def page(pid="p1", title="가짜식당", key="", site="가짜사이트", selection="선정", stage="", deadline=None,
         visit=None, kind="", notified="", days=None, url=None):
    return {
        "id": pid,
        "url": f"https://www.notion.so/{pid}",
        "properties": {
            ns.TITLE: txt("title", title),
            ns.SITE: sel(site),
            ns.KEY: txt("rich_text", key),
            ns.SELECTION: sel(selection),
            ns.STAGE: sel(stage),
            ns.DEADLINE: dt(deadline),
            ns.VISIT: dt(visit),
            ns.KIND: sel(kind),
            ns.NOTIFIED: txt("rich_text", notified),
            ns.DAYS_LEFT: {"number": days},
            ns.URL: {"url": url},
            ns.SELECTED_AT: dt(None),
        },
    }


class FakeNotion:
    """httpx.MockTransport 핸들러. 요청을 기록하고 준비된 응답을 돌려준다."""

    def __init__(self, pages=None, status=200):
        self.requests = []
        self.pages = pages or []
        self.status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, request.url.path, body, dict(request.headers)))
        if self.status != 200:
            return httpx.Response(self.status, json={"message": "boom"}, headers={"Retry-After": "0"})
        if request.url.path.endswith("/query"):
            return httpx.Response(200, json={"results": self.pages, "has_more": False})
        if request.url.path.endswith("/databases"):
            return httpx.Response(200, json={"id": "new-db", "url": "https://www.notion.so/new-db"})
        return httpx.Response(200, json={})


def make(fake):
    http = httpx.Client(base_url="https://api.notion.com/v1", transport=httpx.MockTransport(fake))
    return NotionClient("secret-token-xyz", client=http, sleep=lambda s: None)


def test_parse_notion_id_from_link_and_raw_id():
    expected = "01234567-89ab-cdef-0123-456789abcdef"
    assert parse_notion_id(f"https://app.notion.com/p/{SAMPLE_ID}?source=copy_link") == expected
    assert parse_notion_id(f"https://www.notion.so/내-페이지-{SAMPLE_ID}") == expected
    assert parse_notion_id(expected) == expected
    # 제목이 a-f 로 끝나도 제목 글자가 id 에 섞이지 않는다
    assert parse_notion_id(f"https://www.notion.so/ws/Home-Page-{SAMPLE_ID}") == expected
    with pytest.raises(NotionError):
        parse_notion_id("https://notion.so/no-id-here")


def test_create_database_sends_schema_and_returns_id():
    fake = FakeNotion()
    result = create_database(make(fake), "parent-id", ["강남맛집", "리뷰노트"])
    assert result == {"id": "new-db", "url": "https://www.notion.so/new-db"}
    method, path, body, headers = fake.requests[0]
    assert (method, path) == ("POST", "/v1/databases")
    assert body["parent"] == {"type": "page_id", "page_id": "parent-id"}
    props = body["properties"]
    assert props[ns.TITLE] == {"title": {}}
    assert [o["name"] for o in props[ns.SITE]["select"]["options"]] == ["강남맛집", "리뷰노트", "기타"]
    assert [o["name"] for o in props[ns.STAGE]["select"]["options"]] == ns.STAGES
    assert headers["notion-version"] == "2022-06-28" and headers["authorization"] == "Bearer secret-token-xyz"


def test_schema_separates_human_and_agent_columns_and_has_everything_rules_need():
    props = ns.database_properties(["A"])
    for name in (ns.DEADLINE, ns.VISIT, ns.STAGE, ns.KIND, ns.NOTIFIED, ns.KEY, ns.DAYS_LEFT, ns.SELECTION):
        assert name in props
    assert ns.OTHER_SITE in [o["name"] for o in props[ns.SITE]["select"]["options"]]


def test_manual_row_defaults_to_selected_and_progress_needed():
    c = page_to_campaign(page(deadline="2026-11-30", selection=""))
    assert c.status == Status.SELECTED and c.site == "manual" and c.campaign_id == "p1"
    assert c.review_deadline == date(2026, 11, 30) and c.ref == "p1"
    assert c.url == "https://www.notion.so/p1"  # 링크 칸이 비었으면 Notion 페이지 주소


def test_stage_and_selection_map_to_status():
    assert page_to_campaign(page(stage="체험완료")).status == Status.VISITED
    assert page_to_campaign(page(stage="작성완료")).status == Status.DONE
    assert page_to_campaign(page(stage="예약완료")).status == Status.SELECTED
    assert page_to_campaign(page(selection="탈락")).status == Status.REJECTED
    assert page_to_campaign(page(selection="신청")).status == Status.APPLIED


def test_auto_row_key_notified_visit_and_kind_are_read():
    c = page_to_campaign(page(key="gangnam:123", notified="selected,d-3", visit="2026-10-20T12:00:00+09:00",
                              kind="방문형", site="강남맛집", days=5, url="https://example.kr/c/1"))
    assert (c.site, c.campaign_id, c.key) == ("gangnam", "123", "gangnam:123")
    assert c.notified == {"selected", "d-3"} and c.visit_date == date(2026, 10, 20)
    assert c.kind == "방문형" and c.site_name == "강남맛집" and c.shown_days_left == 5
    assert c.url == "https://example.kr/c/1"


def test_fetch_rows_filters_out_finished_and_paginates():
    class Paged(FakeNotion):
        def __call__(self, request):
            body = json.loads(request.content)
            self.requests.append((request.method, request.url.path, body, {}))
            if "start_cursor" not in body:
                return httpx.Response(200, json={"results": [page("p1")], "has_more": True, "next_cursor": "c2"})
            return httpx.Response(200, json={"results": [page("p2")], "has_more": False})

    fake = Paged()
    rows = NotionStore(make(fake), DB).fetch_rows()
    assert [r.ref for r in rows] == ["p1", "p2"]
    flt = fake.requests[0][2]["filter"]["or"]
    assert {"property": ns.STAGE, "select": {"is_empty": True}} in flt
    assert {"property": ns.STAGE, "select": {"does_not_equal": "작성완료"}} in flt
    assert fake.requests[1][2]["start_cursor"] == "c2"


def test_mark_notified_and_days_left_write_only_agent_columns():
    fake = FakeNotion()
    store = NotionStore(make(fake), DB)
    c = Campaign("manual", "p1", "t", Status.SELECTED, notified={"selected", "d-3"}, ref="p1")
    store.mark_notified(c)
    store.set_days_left(c, 2)
    (_, path1, body1, _), (_, path2, body2, _) = fake.requests
    assert path1 == path2 == "/v1/pages/p1"
    assert list(body1["properties"]) == [ns.NOTIFIED]
    assert body1["properties"][ns.NOTIFIED]["rich_text"][0]["text"]["content"] == "d-3,selected"
    assert body2 == {"properties": {ns.DAYS_LEFT: {"number": 2}}} and c.shown_days_left == 2


def test_upsert_adds_new_and_never_touches_human_columns():
    fake = FakeNotion()
    store = NotionStore(make(fake), DB)
    existing = page_to_campaign(page("p9", key="s:1", deadline="2026-11-01", stage="예약완료"))
    new = Campaign("s", "2", "신규", Status.SELECTED, review_deadline=date(2026, 12, 1), site_name="사이트S")
    same_but_new_deadline = Campaign("s", "1", "기존", Status.SELECTED, review_deadline=date(2026, 11, 5))
    added, updated = store.upsert_collected([new, same_but_new_deadline], [existing])
    assert (added, updated) == (1, 1)
    create_body = fake.requests[0][2]
    assert create_body["parent"] == {"database_id": DB}
    assert ns.STAGE not in create_body["properties"] and ns.NOTIFIED not in create_body["properties"]
    assert create_body["properties"][ns.KEY]["rich_text"][0]["text"]["content"] == "s:2"
    patch_body = fake.requests[1][2]
    assert set(patch_body["properties"]) == {ns.DEADLINE}  # 진행단계 등 사람 칸은 그대로


def test_errors_never_contain_the_token():
    for status in (400, 404):
        with pytest.raises(NotionError) as e:
            NotionStore(make(FakeNotion(status=status)), DB).fetch_rows()
        assert "secret-token-xyz" not in str(e.value) and str(status) in str(e.value)

    def boom(request):
        raise httpx.ConnectError("failed for Bearer secret-token-xyz")

    api = NotionClient("secret-token-xyz", client=httpx.Client(base_url="https://api.notion.com/v1", transport=httpx.MockTransport(boom)), sleep=lambda s: None)
    with pytest.raises(NotionError) as e:
        NotionStore(api, DB).fetch_rows()
    assert "secret-token-xyz" not in str(e.value)


def test_rate_limit_is_retried():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429, json={"message": "slow down"}, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"results": [], "has_more": False})

    api = NotionClient("t", client=httpx.Client(base_url="https://api.notion.com/v1", transport=httpx.MockTransport(handler)), sleep=lambda s: None)
    assert NotionStore(api, DB).fetch_rows() == [] and len(calls) == 3
