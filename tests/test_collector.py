import httpx
import pytest

from review_campaign_agent.catalog import Site, load_catalog
from review_campaign_agent.collectors import (
    COLLECTORS,
    ERROR,
    OK,
    SKIPPED,
    collect_sites,
    format_reports,
    has_error,
    run_collection,
)
from review_campaign_agent.collectors.base import Collector, LoginError
from review_campaign_agent.collectors.reviewplace import (
    ORIGIN,
    ReviewplaceCollector,
    days_left,
    looks_like_login_page,
    parse_campaigns,
)
from review_campaign_agent.models import Status

TODAY = "2026-11-09"

# 실제 화면(공개 캠페인 목록)의 카드 골격을 그대로 쓰되 값만 가상으로 바꿨다.
LIST_HTML = """
<html><body>
<div class="campaign_list01 c_list" id="cmp_join">
  <div class="item"><a href="/pr/?id=111111&rp_apply_refresh=test">
    <div class="img"><img src="/thumb1.png"></div>
    <div class="item_info">
      <div class="txt_wrap"><p class="tit">[블로그] 가상 캠페인 하나</p><p class="txt">가상 제공 내역 하나 </p></div>
      <div class="date_wrap"><p class="date"><em class="d_ico">D</em> - 2</p>
        <div class="num"><p>신청 1169<span> / 10명</span></p></div></div>
    </div></a></div>
  <div class="item"><a href="https://reviewplace.co.kr/pr/?id=222222">
    <div class="item_info">
      <div class="txt_wrap"><p class="tit">[인스타] 가상 구매평 캠페인</p><p class="txt">가상 제공 내역 둘</p></div>
      <div class="date_wrap"><p class="date">오늘마감</p>
        <div class="num"><p>신청 42<span> / 5명</span></p></div></div>
    </div></a></div>
  <div class="item"><a href="/pr/?id=333333">
    <div class="item_info">
      <div class="txt_wrap"><p class="tit">[블로그] 가상 캠페인 셋</p></div>
      <div class="date_wrap"><p class="date"><em class="d_ico">D</em> + 3</p></div>
    </div></a></div>
  <div class="item"><a href="/pr/?id=111111"><p class="tit">같은 캠페인을 가리키는 두 번째 링크</p><p class="date">D - 2</p></a></div>
  <div class="item"><a href="/pr/?page=2"><p>번호 없는 링크</p></a></div>
  <div class="item"><a href="/bd/?tb=notice&amp;id=285"><p>공지 링크</p></a></div>
</div>
</body></html>
"""

LOGIN_PAGE = """
<form name="flogin" action="https://www.reviewplace.co.kr/bbs/login_check.php" method="post">
  <input type="hidden" name="url" value="https%3A%2F%2Fwww.reviewplace.co.kr">
  <input type="text" name="mb_id" id="login_id">
  <input type="password" name="mb_password" id="login_pw">
  <button type="submit">로그인</button>
</form>
"""

# 비로그인으로 선정 목록을 열었을 때 사이트가 돌려주는 화면 (HTTP 200 + alert)
GATE_HTML = """
<script>
alert("회원만 접근 가능합니다. 로그인 해주세요.");
document.location.replace("/bbs/login.php?url=/my/cmp_select.php");
</script>
<noscript><p>회원만 접근 가능합니다. 로그인 해주세요.</p></noscript>
"""


def today():
    from datetime import date

    return date.fromisoformat(TODAY)


class FakeReviewplace:
    """httpx.MockTransport 핸들러. 로그인 성공/실패와 쿠키 전달을 흉내 낸다."""

    def __init__(self, list_html=LIST_HTML, gate=False):
        self.list_html = list_html
        self.gate = gate
        self.requests = []
        self.login_body = ""
        self.list_cookie = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/bbs/login.php":
            return httpx.Response(
                200, text=LOGIN_PAGE, headers={"set-cookie": "PHPSESSID=sess1; Path=/"}
            )
        if path == "/bbs/login_check.php":
            self.login_body = request.content.decode()
            if self.gate:
                return httpx.Response(200, text='<script>alert("아이디나 비밀번호가 틀립니다.");</script>')
            return httpx.Response(200, text='<script>location.replace("/my/cmp_select.php");</script>')
        if path == "/my/cmp_select.php":
            self.list_cookie = request.headers.get("cookie", "")
            return httpx.Response(200, text=GATE_HTML if self.gate else self.list_html)
        return httpx.Response(404)


def client_for(handler: FakeReviewplace) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=ORIGIN, follow_redirects=True)


def test_parse_campaigns_reads_cards():
    camps = parse_campaigns(LIST_HTML, today())
    assert [c.campaign_id for c in camps] == ["111111", "222222", "333333"]

    first = camps[0]
    assert first.key == "reviewplace:111111"
    assert first.title == "[블로그] 가상 캠페인 하나"
    assert first.kind is None
    assert first.status is Status.SELECTED
    assert first.review_deadline.isoformat() == "2026-11-11"  # D-2
    assert first.selected_at.isoformat() == TODAY
    assert first.url == ORIGIN + "/pr/?id=111111&rp_apply_refresh=test"
    assert first.site_name == "리뷰플레이스"

    assert camps[1].kind == "구매평"
    assert camps[1].review_deadline.isoformat() == TODAY  # 오늘마감
    assert camps[1].url == ORIGIN + "/pr/?id=222222"  # 절대 주소도 사이트 경로로 맞춘다

    assert camps[2].review_deadline.isoformat() == "2026-11-06"  # D+3 (마감 지남)


def test_days_left_variants():
    assert days_left(" D - 7 ") == 7
    assert days_left("오늘 마감") == 0
    assert days_left("D +2") == -2
    assert days_left("마감일 미정") is None


def test_parse_campaigns_without_cards_returns_empty():
    assert parse_campaigns(GATE_HTML, today()) == []


def test_parse_campaigns_skips_cards_without_dday_or_applied():
    html = """
    <html><body>
      <div class="item"><a href="/pr/?id=999001"><p class="tit">신청한 캠페인</p><button>취소</button><p>발표 3일 남음</p></a></div>
      <div class="item"><a href="/pr/?id=999002"><p class="tit">마감일 없는 캠페인</p></a></div>
      <div class="item"><a href="/pr/?id=999003"><p class="tit">선정된 캠페인</p><p class="date">D - 4</p></a></div>
    </body></html>
    """
    camps = parse_campaigns(html, today())
    assert len(camps) == 1
    assert camps[0].campaign_id == "999003"
    assert camps[0].title == "선정된 캠페인"


def test_looks_like_login_page():
    assert looks_like_login_page(GATE_HTML)
    assert looks_like_login_page(LOGIN_PAGE)
    assert not looks_like_login_page(LIST_HTML)


def test_login_and_collect_keeps_session_cookie():
    fake = FakeReviewplace()
    camps = ReviewplaceCollector("가상아이디", "가상비밀번호").collect(today(), client=client_for(fake))

    assert [c.campaign_id for c in camps] == ["111111", "222222", "333333"]
    body = fake.login_body
    assert "mb_id=%EA%B0%80%EC%83%81%EC%95%84%EC%9D%B4%EB%94%94" in body  # 가상아이디
    assert "url=%2Fmy%2Fcmp_select.php" in body
    assert "auto_login=1" in body
    assert "PHPSESSID=sess1" in (fake.list_cookie or "")  # 로그인 세션이 목록 요청에 실려 간다


def test_login_failure_raises_without_leaking_credentials():
    fake = FakeReviewplace(gate=True)
    with pytest.raises(LoginError) as exc:
        ReviewplaceCollector("가상아이디", "가상비밀번호").collect(today(), client=client_for(fake))

    message = str(exc.value)
    assert "로그인에 실패" in message
    assert "가상비밀번호" not in message and "가상아이디" not in message


def test_collect_sites_skips_site_without_credentials():
    reports = collect_sites(load_catalog(), {}, today())
    # 수집기가 등록된 사이트는 계정 환경변수가 없으면 '건너뜀'으로 남는다 (설정하지 않은 사용자는 조용히 지나간다).
    assert [r.key for r in reports] == ["gangnam", "dinnerqueen", "reviewplace", "popomon", "seoulouba"]
    assert all(r.status == SKIPPED for r in reports)
    assert not has_error(reports)
    assert "건너뜀" in format_reports(reports)[0]


def test_collect_sites_reports_error_and_keeps_going(monkeypatch):
    class Dummy(Collector):
        key = "dummy"
        name = "가상사이트"
        origin = "https://example.com"

        def _collect(self, client, day):
            return []

    monkeypatch.setitem(COLLECTORS, "dummy", Dummy)
    sites = [
        Site("reviewplace", "리뷰플레이스", "reviewplace.co.kr"),
        Site("dummy", "가상사이트", "example.com"),
    ]
    env = {"REVIEWPLACE_ID": "u", "REVIEWPLACE_PW": "p", "DUMMY_ID": "u", "DUMMY_PW": "p"}
    fake = FakeReviewplace(gate=True)

    reports = collect_sites(sites, env, today(), client_factory=lambda cls: client_for(fake))

    assert [r.status for r in reports] == [ERROR, OK]
    assert has_error(reports)
    lines = format_reports(reports)
    assert lines[0].startswith("리뷰플레이스: 실패 — ")
    assert lines[1] == "가상사이트: 0건 확인"


class FakeStore:
    def __init__(self):
        self.rows_read = 0
        self.upserts = []

    def fetch_rows(self):
        self.rows_read += 1
        return []

    def upsert_collected(self, campaigns, rows):
        self.upserts.append(list(campaigns))
        return len(campaigns), 0


def _sites():
    return [Site("reviewplace", "리뷰플레이스", "reviewplace.co.kr")]


def _env():
    return {"REVIEWPLACE_ID": "u", "REVIEWPLACE_PW": "p"}


def test_run_collection_writes_to_store():
    store = FakeStore()
    fake = FakeReviewplace()

    reports = run_collection(
        store, _sites(), _env(), today(), client_factory=lambda cls: client_for(fake)
    )

    assert store.rows_read == 1
    assert len(store.upserts) == 1
    assert reports[0].status == OK
    assert reports[0].added == 3
    assert "새로 추가 3" in format_reports(reports)[0]


def test_run_collection_dry_run_does_not_write():
    store = FakeStore()
    fake = FakeReviewplace()

    reports = run_collection(
        store, _sites(), _env(), today(), dry_run=True, client_factory=lambda cls: client_for(fake)
    )

    assert store.upserts == [] and store.rows_read == 0
    assert reports[0].count == 3
